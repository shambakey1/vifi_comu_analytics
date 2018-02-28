'''
Created on Feb 25, 2018

@author: Mohammed Elshambakey
@contact: shambakey1@gmail.com
'''

import yaml, time, os, sys, shutil, docker, json, uuid, requests, docker
from typing import List
from spyder.widgets.tests import test_findinfiles

############## User Defined Server Control Function ##############
def check_docker_service_complete(service_id:str,task_num_in:int,ttl:int=service_ttl)->bool:
	""" Check if specified Docker service has finished currently or within specified time threshold.
	@param service_id: Service ID
	@type service_id: str
	@param task_num: Number of replicas for the input @service_id
	@type task_num: int
	@param ttl: Time interval within which @service_id should have finished
	@type ttl: int
	@return: True if all tasks (i.e., replicas) of the @service_id are complete. Otherwise, false
	@rtype: bool      
	"""
	
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

def load_conf(infile:str)->dict:
	''' Loads user configuration file. "infile" is in JSON format
	@param infile: Path and name of the user input JSON configuration file
	@type infile: str  
	@return: User configuration file as JSON object
	@rtype: dict
	'''

	if not infile:
		print('Error: No user configuration file is specified')
	elif not os.path.isfile(infile):
		print('Error: No user configuration file is specified')
	else:	
		try:
			with open(infile, 'r') as f:
				inputs=json.load(f)
			return inputs
		except:
			print('Error occurred when opening user input configuration file: '+sys.exc_info()[0])

def check_input_files(in_file_root_loc:str,conf_in_total:List[str])->bool:
	'''Checks if all user input files and directories exist. It returns true if all exists
	@param in_file_root_loc: Root path location of the user request folder
	@type in_file_root_loc: str
	@param conf_in_total: List of required input files/directories to execute user request
	@type conf_in_total: List[str]  
	'''

	try:
		for f in conf_in_total:
			if not os.path.exists(os.path.join(in_file_root_loc,f)):
				print('Error: Could not find user required input file/directory '+os.path.join(in_file_root_loc,f))
				return False
		return True
	except:
		print('Error when checking user input files and folders: '+sys.exc_info()[0])
		return False

def getPromMetricsNames(prom_path:str=conf['Prometheus_parameters']['prometheus_url'],\
					uname:str=conf['Prometheus_parameters']['uname'],upass:str=conf['Prometheus_parameters']['upass'],\
					fname:str=conf['Prometheus_parameters']['metrics_names_f'], \
					fname_path:str=conf['Prometheus_parameters']['metrics_names_path'])->List[str]:
	''' Retrive Prometheus metrics names and write them to output file if required in JSON structure 
	@param prom_path: Prometheus API url
	@type prom_path: str  
	@param uname: Prometheus username. Default is 'admin'
	@type uname: str
	@param upass: Prometheus password. Defaul is 'admin'
	@type upass: str
	@param fname: File path to record metrics names
	@type fname: str
	@param fname_path: Path to store @fname
	@type fname_path: str  
	@return: List of metrics names
	@rtype: List[str]	  
	'''
	
	metrics_req=requests.get(prom_path+"label/__name__/values",auth=(uname,upass))
	metrics_names=[] # List containing 
	if metrics_req.ok: # Check Prometheus can be contacted
		metrics_names=metrics_req.json()['data']
		if not metrics_names: # Check metrics names is not empty
			print('Prometheus has no metrics')
			sys.exit()
	else:
		print("Could not get metrics names from Prometheus")
		sys.exit()
		
	if fname: # Dump metrics names as a JSON file if a JSON file path is provided
		with open(os.path.join(fname_path,fname),'w') as f:
			json.dump(metrics_names, f)
	return metrics_names # Return metrics names

def getMetricsNames(metrics_f:str)-> List[str]:
	''' Read metrics names from JSON file. Useful when only a subset of metrics are required
	@param metrics_f: Path and name of JSON file containing metrics names
	@type metrics_f: str
	@return: List of metrics
	@rtype: List[str]
	'''
	
	with open(metrics_f, 'r') as f:
		return json.load(f)

def getMetricsValues(m:List[str], start_t:float=None,end_t:float=None, prom_path:str=conf['Prometheus_parameters']['prometheus_url'],\
					step:int=conf['Prometheus_parameters']['query_step'],\
					uname:str=conf['Prometheus_parameters']['uname'],upass:str=conf['Prometheus_parameters']['upass'],\
					write_to_file:bool=conf['Prometheus_parameters']['write_metrics'], fname:str=conf['Prometheus_parameters']['metrics_values_f'], \
					fname_path:str=conf['Prometheus_parameters']['metrics_values_path'])->dict:
	''' Get specified metric values for specified duration if start and end times of duration are specified
	If either start or end times are not specified, then query is done only at the time instance that is specified by either of them.
	@param m: Metric name
	@type m: str 
	@param prom_path: Prometheus API url 
	@type prom_path: str
	@param start_t: Start time to collect metric's time series values (Unix Time Stamp). Defaults to current time. If not specified, the query is done at a single time instance specified by @end_t. At least @start_t and/or @end_t should be specified.
	@type start_t: float 
	@param end_t: End time to collect metric's time series values (Unix Time Stamp). Defaults to current time. If not specified, the query is done at a single time instance specified by @start_t. At least @start_t and/or @end_t should be specified.
	@type end_t: float   
	@param step: Time step during query interval
	@type step: int
	@param uname: Prometheus username
	@type uname: str
	@param upass: Prometheus user password
	@type upass: str
	@param write_to_file: If set, then write output metric(s) values to specified file if one is specified by @fname under specified path given by @fname_path. If @fname is not specified, then create separate file for each metric.
	@type write_to_file: bool
	@param fname: File name to record output metric(s) values under specified path given by @fname_path. If not specified while @write_to_file is set, then a separate file is created for each metric.
	@type fname: str
	@param fname_path: Path of @fname. Defaults to current directory
	@type fname_path: str 
	@return: Metric(s) values for the specified time interval at the specified steps, or at a specific time instance
	@rtype: dict
	'''
	#TODO: If start_t is not specified, then start query from the earliest possible timedate. But this depeneds on how long Prometheus stores data series, and the incremental step
	
	res=None
	res_values={}	# Initial metric values is empty

	if start_t and not end_t:
		end_t=start_t
	elif end_t and not start_t:
		start_t=end_t
	elif not start_t and not end_t: 
		start_t=end_t=time.time()
	elif start_t>end_t:	# Query metric values within time interval
		print("Error: start time cannot be greater than end time to collect metric data")
		sys.exit()
		
	for mi in m:
		res=requests.get(prom_path+"query_range",auth=(uname,upass),params={'query':mi,'start':start_t,'end':end_t,'step':step})
		if res.ok: # Check Prometheus can be contacted for current metric
			res_values[mi]=res.json()['data']['result']
		else:
			res_values[mi]="Error: cannot contact Prometheus for metric "+mi
			
	if write_to_file:
		if fname: # Dump metric values as a JSON file if one is provided
			with open(os.path.join(fname_path,fname),'w') as f:
				json.dump(res_values, f)
		else:	# Dump each metric values in a separate JSON file if no JSON file is provided
			for mi in m:
				with open(os.path.join(fname_path,mi+'_'+str(start_t)+'_'+str(end_t)+'.json'),'w') as f:
					json.dump(res_values[mi],f)
			
	return res_values # Return metrics names

def vifi_run():
	''' VIFI request analysis and processing procedure '''

	### LOAD VIFI CONFIGURATION FILE ###
	with open('vifi_config.yml','r') as f:
		conf=yaml.load(f)
		
	service_ttl=conf['docker']['ttl'] # Default ttl for each (Docker) service
	
	### START DOCKER CLIENT ###
	client=docker.from_env()
	
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
			f_log.flush()
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
	#			shutil.move(script_processed,script_finished)
				f_log.write("FINISHED at "+repr(time.time())+"\n\n")
				f_log.flush()
				shutil.move(script_processed,script_finished)
				# COPY REQUIRED RESULT FILES FOR FURTHER PROCESSING OR TRANSFER
	#			for root, dirs, files in os.walk(script_finished):
	#				if dirs==req_res_path_per_request:
	#                                        continue
	#				for f_res in files:
	#					if f_res in conf_in[result_files_key]:
				for f_res in conf_in[result_files_key]:
				#			shutil.copy(os.path.join(root,f_res),os.path.join(script_finished,req_res_path_per_request))
					shutil.copy(os.path.join(script_finished,f_res),os.path.join(script_finished,req_res_path_per_request))
							# JUST FOR THIS SCRIPT, TRANSFER REQUIRED RESULT FILES TO S3 BUCKET
					if conf_in[s3_transfer_key] and conf_in[s3_buc_key]:      # s3_transfer is True and s3_buc has some value
					        import boto3
					        s3 = boto3.resource('s3')
						data = open(os.path.join(script_finished,f_res), 'rb')
						key_obj=conf_in[userid_kye]+"/"+conf_in[s3_loc_under_userid_key]+"/"+f_res
						s3.Bucket(conf_in[s3_buc_key]).put_object(Key=key_obj, Body=data)	    # In this script, we do not need AWS credentials, as this EC2 instance has the proper S3 rule
			else:
	#			os.remove(os.path.join(script_processed,general_python_script_name))	# This step cannot be done before the "if condition". Otherwise, the file will be removed before docker task finishes
				shutil.move(script_processed,script_failed)
				f_log.write("FAILED at "+repr(time.time())+"\n\n")
				f_log.flush()
			# DELTE DOCKER SERVICE
			try:
	                        client.services.get(service_name).remove()
	                except:
	                        pass
	f_log.close()
	
if __name__ == '__main__':
	pass