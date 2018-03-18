'''
Created on Oct 16, 2016

@author: Mohammed Elshambakey
@contact: shambakey1@gmail.com
'''

import time, os, sys, shutil, docker, json, uuid, requests
from typing import List
from __builtin__ import str


############ GENERAL PARAMETERS ###############
#TODO: This section of general parameters may be moved to outside configuration files
# Key names used in any conf.json file
conf_file_name="conf.json"	# Name of configuration file that should exist in any user request
userid_kye="userid"				# Key for User ID
total_inputs_key="total_inputs"			# Key for all uploaded user input files and folders to this server
main_scripts_key="main_scripts"			# Key for user scripts that will execute inside docker swarm. Main scripts are also included in the total_inputs
result_files_key="result_files"			# Key for output files
s3_transfer_key="s3_transfer"			# Key to define whether to upload output files to S3 bucket or not
s3_buc_key="s3_buc"				# Key for S3 bucket
s3_loc_under_userid_key="s3_loc_under_userid"	# Key for S3 location under userid folder in specified S3 bucket
ser_check_thr_key="ser_check_thr"		# Key for user defined time for executing main scripts
docker_img_key="docker_img"			# Key for Docker image to execute scripts (e.g., python docker image)
docker_cmd_eng_key="docker_cmd_eng"		# Key for command to run main script(s) insdie docker swarm (e.g., python <script_name>)
docker_rep_key="docker_rep"			# Key for number of docker tasks. Useful for parallelization.
data_dir_container_key="data_dir_container"	# Key for data location inside each docker task

############ PROMETHEUS PARAMETERS ###############
uname="admin"					# Prometheus default user name
upass="admin"					# Prometheus default user password
prometheus_url="http://localhost:9090/api/v1/"	# Prometheus default API url
query_step=15					# Steps between consecutive queries time series (Default is 15 sec)
metrics_names_f="metrics_names.json"		# Default output file to record metrics names
metrics_path=""					# Path for results files. Default is current path

######### PATH PARAMETERS FOR INPUT SCRIPTS, OUTPUT DIRECTORIES #################
domain="jpl"
script_path_in="/home/ubuntu/requests/"+domain+"/in"
script_path_out="/home/ubuntu/requests/"+domain+"/finished"
script_path_failed="/home/ubuntu/requests/"+domain+"/failed"
log_path="/home/ubuntu/requests/"+domain+"/log"
general_python_script_path="/home/ubuntu/requests"
#general_python_script_name="shambakey1_general.py"
req_res_path_per_request="results"

######### DOCKER (SWARM) PARAMETERS ##############
container_dir="/home"
work_dir=container_dir
docker_img="shambakey1/ocw"
docker_cmd_eng=""
docker_rep="1"
data_dir="/home/ubuntu/data_GPM"	# Result from data management layer
data_dir_container=""
climate_dir="/home/ubuntu/climate"
climate_dir_container="/climate"

############ START DOCKER CLIENT ###############
client=docker.from_env()

############## User Defined Server Control Function ##############
def check_docker_service_complete(service_id,task_num_in,ttl=300):
	"""Check if specified Docker service has finished currently or within specified time threshold."""
	
	### Checks if each task in task_num has completed
	while ttl:
		try:
			ser=client.services.get(service_id)
			task_num=task_num_in
			for t in ser.tasks():
				if t["Status"]["State"]=="complete":
					task_num-=1
			if task_num==0:
				return True
		except:
			pass
			ttl-=1
			time.sleep(1)
	return False

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

############ USER PARAMETERS (MAY NOT BE NEEDED ANY MORE AS CONFIGURATION FILE READ FROM USER INPUT) #######################
main_scripts=[]
result_files=[]
s3_buc=""
s3_transfer=False		# If True, transfer required results to the specified S3 bucket
ser_check_thr=300  # Threshold time to check if docker service is complete
#s3_buc="s3://uncc-vifi-bucket"

############### LOGGING PARAMETERS #######################
f_log_path=os.path.join(log_path,"out.log")
f_log = open(f_log_path, 'a')
f_log.write("Scheduled by NIFI at "+repr(time.time())+"\n\n")

######### LOOP THROUGH REQUESTS AND PROCESS THEM (CURENTLY PROCESSING LOCATION IS NFS SHARED) ##########
request_in=os.listdir(script_path_in)
for request in request_in:

	# Load configuration file if exists in current request and override server settings. Otherwise, move to the next request
	if os.path.exists(os.path.join(script_path_in,request,conf_file_name)):
		conf_in=load_conf(os.path.join(script_path_in,request,conf_file_name))
		if conf_in[docker_rep_key]:
			docker_rep=conf_in[docker_rep_key]
		if conf_in[docker_img_key]:
			docker_img=conf_in[docker_img_key]
		if conf_in[ser_check_thr_key]:
			ser_check_thr=conf_in[ser_check_thr_key]
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
	os.mkdir(os.path.join(os.path.join(script_path_in,request),req_res_path_per_request))	# To keep only required result files to be further processed or transfered.

	script_in=os.listdir(os.path.join(script_path_in,request))
#	shutil.copy(os.path.join(general_python_script_path,general_python_script_name),os.path.join(script_path_in,request))
	for f in conf_in[main_scripts_key]:
		service_name=os.path.splitext(os.path.split(f)[1])[0]
#		docker_cmd_script=general_python_script_name
#		docker_cmd="python "+docker_cmd_script	#TODO: the general 'shambakey1.py' should be removed somehow
		docker_cmd=conf_in[docker_cmd_eng_key]+" "+f
		############ PRECAUTION: REMOVE DOCKER SERVICE IF ALREADY EXISTS ###########
		try:
					client.services.get(service_name).remove()
			except:
					pass

		############ BUILD THE NEW SERVICE ################
		os.chmod(os.path.join(script_path_in,request),0777)	# Just a precaution for the following docker tasks
				script_processed=os.path.join(script_path_in,request)
				script_finished=os.path.join(script_path_out,request)
				script_failed=os.path.join(script_path_failed,request)
		cmd="docker service create --name "+service_name+" --replicas "+docker_rep+" --restart-condition=on-failure --mount type=bind,source="+os.path.join(script_path_in,request)+",destination="+container_dir+" --mount type=bind,source="+data_dir+",destination="+conf_in[data_dir_container_key]+" --mount type=bind,source="+climate_dir+",destination="+climate_dir_container+" -w "+work_dir+" --env MY_TASK_ID={{.Task.Name}} --env PYTHONPATH="+climate_dir_container+" --env SCRIPTFILE="+f+" "+docker_img+" "+docker_cmd
		f_log.write(repr(time.time())+":"+cmd+"\n")	# Log the command
		try:
			os.system(cmd)
		except:
			f_log.write("Unexpected error:"+ sys.exc_info()[0]+"\n")

		########### CLEAN ONLY AFTER MAKING SURE OUTPUT IS SENT TO USER ##############
#		script_processed=os.path.join(script_path_in,request)
#		script_finished=os.path.join(script_path_out,request)
#		script_failed=os.path.join(script_path_failed,request)
		if check_docker_service_complete(service_name,int(docker_rep),int(ser_check_thr)):
			# REMOVE UN-NEEDED FILES
#			os.remove(os.path.join(script_processed,general_python_script_name))	# This step cannot be done before the "if condition". Otherwise, the file will be removed before docker task finishes
			f_log.write("FINISHED at "+repr(time.time())+"\n\n")
						shutil.move(script_processed,script_finished)
			# COPY REQUIRED RESULT FILES FOR FURTHER PROCESSING OR TRANSFER
#			for root, dirs, files in os.walk(script_finished):
#				if dirs==req_res_path_per_request:
#										continue
#				for f_res in files:
#					if f_res in conf_in[result_files_key]:
			for f_res in conf_in[result_files_key]:
			#			shutil.copy(os.path.join(root,f_res),os.path.join(script_finished,req_res_path_per_request))
				shutil.copy(os.path.join(script_finished,f_res),os.path.join(script_finished,req_res_path_per_request))
						# JUST FOR THIS SCRIPT, TRANSFER REQUIRED RESULT FILES TO S3 BUCKET
				if conf_in[s3_transfer_key] and conf_in[s3_buc_key]:	  # s3_transfer is True and s3_buc has some value
						import boto3
						s3 = boto3.resource('s3')
					data = open(os.path.join(script_finished,f_res), 'rb')
					key_obj=conf_in[userid_kye]+"/"+conf_in[s3_loc_under_userid_key]+"/"+f_res
					s3.Bucket(conf_in[s3_buc_key]).put_object(Key=key_obj, Body=data)		# In this script, we do not need AWS credentials, as this EC2 instance has the proper S3 rule
		else:
#			os.remove(os.path.join(script_processed,general_python_script_name))	# This step cannot be done before the "if condition". Otherwise, the file will be removed before docker task finishes
			shutil.move(script_processed,script_failed)
			f_log.write("FAILED at "+repr(time.time())+"\n\n")
		# DELTE DOCKER SERVICE
		try:
						client.services.get(service_name).remove()
				except:
						pass
f_log.close()
