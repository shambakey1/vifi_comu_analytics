from eppy import modeleditor
from eppy.modeleditor import IDF
import argparse, json, sys, time, os, shutil, uuid

# Key names used in any conf.json file
conf_file_name="conf.json"      # Name of configuration file that should exist in any user request
userid_kye="userid"                             # Key for User ID
total_inputs_key="total_inputs"                 # Key for all uploaded user input files and folders to this server
main_scripts_key="main_scripts"                 # Key for user scripts that will execute inside docker swarm. Main scripts are also included in the total_inputs
result_files_key="result_files"                 # Key for output files
s3_transfer_key="s3_transfer"                   # Key to define whether to upload output files to S3 bucket or not
s3_buc_key="s3_buc"                             # Key for S3 bucket
s3_loc_under_userid_key="s3_loc_under_userid"   # Key for S3 location under userid folder in specified S3 bucket
ser_check_thr_key="ser_check_thr"               # Key for user defined time for executing main scripts
docker_img_key="docker_img"                     # Key for Docker image to execute scripts (e.g., python docker image)
docker_cmd_eng_key="docker_cmd_eng"             # Key for command to run main script(s) insdie docker swarm (e.g., python <script_name>)
docker_rep_key="docker_rep"                     # Key for number of docker tasks. Useful for parallelization.
data_dir_container_key="data_dir_container"     # Key for data location inside each docker task

############## User Defined Server Control Function ##############
def load_conf(infile):
        '''Loads user configuration file. "infile" is in JSON format.'''

        f_infile=open(infile)
        inputs=json.load(f_infile)
        f_infile.close()
        return inputs

def check_input_files(in_file_root_loc,conf_in_total):
        '''Checks if all user input files and directories exist. It returns true if all exists.'''

        for f in conf_in_total:
                if not os.path.exists(os.path.join(in_file_root_loc,f)):
                        return False
        return True

######### PATH PARAMETERS FOR INPUT SCRIPTS, OUTPUT DIRECTORIES #################
domain="srhbe"
script_path_in="/home/ubuntu/requests/"+domain+"/in"
script_path_out="/home/ubuntu/requests/"+domain+"/finished"
script_path_failed="/home/ubuntu/requests/"+domain+"/failed"
log_path="/home/ubuntu/requests/"+domain+"/log"
general_python_script_path="/home/ubuntu/requests"
#general_python_script_name="shambakey1_general.py"
req_res_path_per_request="results"

######## SPECIFIC PARAMETERS FOR THE SRHBE UPDATE IDF USE CASE #############
idd_f="/home/ubuntu/org/energyplus/EnergyPlus/idd/V8-6-0-Energy+.idd"	# IDD file of E+
IDF.setiddname(idd_f)		# Important step: set the IDD for eppy

############ USER PARAMETERS (MAY NOT BE NEEDED ANY MORE AS CONFIGURATION FILE READ FROM USER INPUT) #######################
main_scripts=[]
result_files=[]
s3_buc=""
s3_transfer=False        # If True, transfer required results to the specified S3 bucket
#ser_check_thr=300  # Threshold time to check if docker service is complete
#s3_buc="s3://uncc-vifi-bucket"

############### LOGGING PARAMETERS #######################
f_log_path=os.path.join(log_path,"out.log")
f_log = open(f_log_path, 'a')
f_log.write("Scheduled by NIFI at "+time.strftime("%c")+"\n\n")

######### LOOP THROUGH REQUESTS AND PROCESS THEM (CURENTLY PROCESSING LOCATION IS NFS SHARED) ##########
request_in=os.listdir(script_path_in)
for request in request_in:

        # Load configuration file if exists in current request and override server settings. Otherwise, move to the next request
        if os.path.exists(os.path.join(script_path_in,request,conf_file_name)):
                conf_in=load_conf(os.path.join(script_path_in,request,conf_file_name))
		if conf_in["idf_f"]:				# Load old input IDF file to be updated
			idf_f=conf_in["idf_f"]
		if conf_in["idf_f_updates"]:			# Load updtes to be applied to old IDF file
			idf_f_updates=conf_in["idf_f_updates"]
		if conf_in["search_terms"]:			# Load search terms (i.e., update criterion)
			search_terms=conf_in["search_terms"]
		if conf_in["idf_f_updated"]:			# Resulting updated IDF file
			idf_f_updated=conf_in["idf_f_updated"]
		else:						# If resulting file not specified, then replace old IDF file with the updated IDF file
			idf_f_updated=idf_f
		conf_in[main_scripts_key].append(conf_in["userid"]+"_updateIDF_"+str(uuid.uuid1()))	# This will be service name for this user
        else:
                f_log.write("Configuration does not exsit for "+request+" at "+repr(time.time())+"\n")
                continue

        # Validate all input files and folders exist before processing. If not all input files and folder exist, move to next request
        if not check_input_files(os.path.join(script_path_in,request),conf_in[total_inputs_key]):
                f_log.write("Some or all inputs files (folders) are missing for "+request+" at "+repr(time.time())+"\n\n")
                continue

        # Now, request can be processed
        # Create 'results' folder (if not already exists) to keep output files. Otherwise, create a 'results' folder with new ID
        if os.path.exists(os.path.join(os.path.join(script_path_in,request),req_res_path_per_request)):
                req_res_path_per_request=req_res_path_per_request+"_"+str(uuid.uuid1())
        os.mkdir(os.path.join(os.path.join(script_path_in,request),req_res_path_per_request))   # To keep only required result files to be further processed or transfered.

        for f in conf_in[main_scripts_key]:
#                service_name=os.path.splitext(os.path.split(f.split()[0])[1])[0]

                ############ BUILD THE UPDATE IDF SERVICE ################
                os.chmod(os.path.join(script_path_in,request),0777)		# Just a precaution for the following docker tasks
                script_processed=os.path.join(script_path_in,request)
                script_finished=os.path.join(script_path_out,request)
                script_failed=os.path.join(script_path_failed,request)
                f_log.write("START "+f+" at "+repr(time.time())+"\n")	 	# Log the update IDF command
		idf_in = IDF(os.path.join(script_processed,idf_f))						# Read input IDF file
		idf_updates=IDF(os.path.join(script_processed,idf_f_updates))					# Read updates to be applied to input IDF file
		for key,val in search_terms.iteritems():
			old_obj=idf_in.getobject(key,val)			# IDF object to be updated
			new_obj=idf_updates.getobject(key,val)			# Updates to the IDF object
			idf_in.removeidfobject(old_obj)				# Remove the old IDF object
			idf_in.copyidfobject(new_obj)				# Add the new IDF object instead of the removed IDF object
		idf_in.saveas(os.path.join(script_processed,idf_f_updated))					# Save modifications to a new updated IDF file
		f_log.write("FINISHED "+f+" at "+repr(time.time())+"\n")	# RECORD END OF UPDATE IDF SERVICE
		shutil.move(script_processed,script_finished)		
		for f_res in conf_in[result_files_key]:
			shutil.copy(os.path.join(script_finished,f_res),os.path.join(script_finished,req_res_path_per_request))
		########## IF S3 TRANSFER, THEN TRANSFER REQUIRED RESULT FILES TO S3 BUCKET
                if conf_in[s3_transfer_key] and conf_in[s3_buc_key]:		# s3_transfer is True and s3_buc has some value
                        import boto3
                        s3 = boto3.resource('s3')
                        data = open(os.path.join(script_finished,f_res), 'rb')
                        key_obj=conf_in[userid_kye]+"/"+conf_in[s3_loc_under_userid_key]+"/"+f_res
                        s3.Bucket(conf_in[s3_buc_key]).put_object(Key=key_obj, Body=data)           # In this script, we do not need AWS credentials, as this EC2 instance has the proper S3 rule

######### FINALLY, CLOSE LOG FILE ###############
f_log.close()
