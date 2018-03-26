'''
Created on Feb 25, 2018

@author: Mohammed Elshambakey
@contact: shambakey1@gmail.com
'''

import yaml, time, os, sys, shutil, docker, json, uuid, requests, docker
from typing import List
#from botocore.vendored.requests.compat import str

def load_conf(infile:str)->dict:
	''' Loads user configuration file. "infile" is in JSON format
	@param infile: Path and name of the user input JSON configuration file
	@type infile: str  
	@return: User configuration file as JSON object
	@rtype: dict
	'''

	try:
		if infile and os.path.isfile(infile):
			with open(infile, 'r') as f:
				inputs=json.load(f)
			return inputs
		else:
			print('Error: No user configuration file is specified')
	except:
		print('Error occurred when opening user input configuration file:')
		print(sys.exc_info())

def check_input_files(in_file_root_loc:str,conf_in_total:List[str])->bool:
	'''Checks if all user input files and directories exist. Returns true if all exists
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
		print('Error when checking user input files and folders:')
		print(sys.exc_info())

def getPromMetricsNames(prom_path:str,uname:str,upass:str,fname:str,fname_path:str)->List[str]:
	''' Retrive Prometheus metrics names and write them to output file if required in JSON structure 
	@param prom_path: Prometheus API url
	@type prom_path: str  
	@param uname: Prometheus username
	@type uname: str
	@param upass: Prometheus password
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

def getMetricsValues(m:List[str], start_t:float,end_t:float,prom_path:str,step:int,uname:str,upass:str,\
					write_to_file:bool,fname:str,fname_path:str)->dict:
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

def loadVIFIConf(conf_f:str)->dict:
	''' Load VIFI configuration and make any necessary initialization for (sub)workflows
	@param conf_f: VIFI configuration file name (in YAML)
	@type conf_f: str 
	'''
	
	try:
		if os.path.isfile(conf_f):	# Check the existence of the general VIFI configuration file
			with open(conf_f,'r') as f:
				conf=yaml.load(f)
			
			# Info for root request directory
			root_script_path=conf['domains']['root_script_path']['name']	# Root directory for different domains requests
			root_script_path_mode=conf['domains']['root_script_path']['mode']	# Mode of requests root directory
			root_script_path_exist=conf['domains']['root_script_path']['exist_ok']	# If true, use already existing folder if one exists
			#FIXME: the following instruction should be used with the proper 'mode' configuration
			#os.makedirs(root_script_path,mode=root_script_path_mode,exist_ok=root_script_path_exist)	# Create requests root directory if not exists
			os.makedirs(root_script_path,exist_ok=root_script_path_exist)	# Create requests root directory if not exists
			
			# Default info for request structure within each domain 
			request_path_in=conf['domains']['script_path_in']['name']	# Path to receive requests within each domain
			request_path_in_mode=conf['domains']['script_path_in']['mode']	# Mode for received requests folder
			request_path_in_exist=conf['domains']['script_path_in']['exist_ok']	# If true, use already existing folder if one exists
			
			request_path_out=conf['domains']['script_path_out']['name']	# Path to output results within each domain
			request_path_out_mode=conf['domains']['script_path_out']['mode']	# Mode for output results folder
			request_path_out_exist=conf['domains']['script_path_out']['exist_ok']	# If true, use already existing folder if one exists
			
			request_path_failed=conf['domains']['script_path_failed']['name']	# Path to failed results within each domain
			request_path_failed_mode=conf['domains']['script_path_failed']['mode']	# Mode for failed results folder
			request_path_failed_exist=conf['domains']['script_path_failed']['exist_ok']	# If true, use already existing folder if one exists
			
			log_path=conf['domains']['log_path']['name']	# Path to logs within each domain
			log_path_mode=conf['domains']['log_path']['mode']	# Mode for logs folder
			log_path_exist=conf['domains']['log_path']['exist_ok']	# If true, use already existing folder if one exists
			
			req_res_path_per_request=conf['domains']['req_res_path_per_request']['name']	# Path to intermediate results folder within each domain
			req_res_path_per_request_mode=conf['domains']['req_res_path_per_request']['mode']	# Mode for logs folder
			req_res_path_per_request_exist=conf['domains']['req_res_path_per_request']['exist_ok']	# If true, use already existing folder if one exists
			
			for d in conf['domains']['sets']:	# Create a sub-directory for each domain under the requests root directory
				#FIXME: the following commented instruction should be used whith the proper 'mode' configuration
				#os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name']),mode=conf['domains']['sets'][d]['mode'],exist_ok=conf['domains']['sets'][d]['exist_ok'])
				#os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],request_path_in),mode=request_path_in_mode,exist_ok=request_path_in_exist)
				#os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],request_path_out),mode=request_path_out_mode,exist_ok=request_path_out_exist)
				#os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],request_path_failed),mode=request_path_failed_mode,exist_ok=request_path_failed_exist)
				#os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],log_path),mode=log_path_mode,exist_ok=log_path_exist)
				#os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],req_res_path_per_request),mode=req_res_path_per_request_mode,exist_ok=req_res_path_per_request_exist)
				os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name']),exist_ok=conf['domains']['sets'][d]['exist_ok'])
				os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],request_path_in),exist_ok=request_path_in_exist)
				os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],request_path_out),exist_ok=request_path_out_exist)
				os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],request_path_failed),exist_ok=request_path_failed_exist)
				os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],log_path),exist_ok=log_path_exist)
				os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],req_res_path_per_request),exist_ok=req_res_path_per_request_exist)
			return conf	
		else:
				print('Error: could not find VIFI general configuration file') 
	except:
		print('Error occurred during loading VIFI configuration file:')
		print(sys.exc_info())
		
def check_docker_service_complete(client,service_id:str,task_num_in:int,ttl:int=300)->bool:
	''' Check if specified Docker service has finished currently or within specified time threshold
	@param client: Client connection to Docker Engine
	@type client: client connection
	@param service_id: Required Service ID whose status is to be checked
	@type service_id: str
	@param task_num: Number of tasks (i.e., replicas) within the service
	@type task_num: int
	@param ttl: Time threshold after which, the service is considered NOT complete
	@type ttl: int  
	@return: True if all tasks of required service are complete. Otherwise, false
	@rtype: bool    
	'''
	
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
			ttl-=1
			time.sleep(1)
	return False
		
def vifi_run(set:str,conf:dict)->None:
	''' VIFI request analysis and processing procedure for a specific set
	@param set: A specific set (i.e., (sub)set) to run (i.e., receive and process requests)
	@type set: str
	@param conf_in: Configuration
	@type conf_in: dict  
	'''

	f_log=''	# Variable of log file
	
	try:
		if set in conf['domains']['sets']: # Check if required set exists
			### INITIALIZE USER PARAMETERS (APPLICABLE FOR ANY USER) ###
			conf_file_name=conf['user_conf']['conf_file_name']

			### INITIALIZE REQUIRED PATH VARIABLES FOR SPECIFIED SET ###
			script_path_in=os.path.join(conf['domains']['root_script_path']['name'],conf['domains']['sets'][set]['name'],\
								conf['domains']['script_path_in']['name'])
			script_path_out=os.path.join(conf['domains']['root_script_path']['name'],conf['domains']['sets'][set]['name'],\
								conf['domains']['script_path_out']['name'])
			script_path_failed=os.path.join(conf['domains']['root_script_path']['name'],conf['domains']['sets'][set]['name'],\
								conf['domains']['script_path_failed']['name'])
			log_path=os.path.join(conf['domains']['root_script_path']['name'],conf['domains']['sets'][set]['name'],\
								conf['domains']['log_path']['name'])
			req_res_path_per_request=os.path.join(conf['domains']['root_script_path']['name'],conf['domains']['sets'][set]['name'],conf['domains']['req_res_path_per_request']['name'])
			data_dir=conf['domains']['sets'][set]['data_dir']
			
			### LOGGING PARAMETERS ###
			f_log_path=os.path.join(log_path,"out.log")
			f_log = open(f_log_path, 'a')
			f_log.write("Scheduled by VIFI Orchestrator at "+str(time.time())+"\n")

			### IF DOCKER IS USED FOR THIS SET, THEN INITIALIZE DEFAULT DOCKER PARAMETERS ###
			### SOME DOCKER PARAMETERS CAN BE OVERRIDEN BY END USER IF ALLOWED ###
			if 'docker' in conf['domains']['sets'][set] and conf['domains']['sets'][set]['docker']:
				container_dir=conf['domains']['sets'][set]['docker']['container_dir']
				work_dir=conf['domains']['sets'][set]['docker']['work_dir']
				docker_img_set=conf['domains']['sets'][set]['docker']['docker_img']	# Set of allowed docker images
				#docker_cmd_eng=conf['domains']['sets'][set]['docker']['docker_cmd_eng']
				docker_rep=conf['domains']['sets'][set]['docker']['docker_rep']
				#data_dir_container=conf['domains']['sets'][set]['docker']['data_dir_container']				
				ser_check_thr=conf['domains']['sets'][set]['docker']['ttl'] # Default ttl for each (Docker) service
				client=docker.from_env()
			else:
				print('Error: No containerization technique and/or stand alone service is specified to run (sub)workflow '+set)
				return
				
			### LOOP THROUGH REQUESTS AND PROCESS THEM (CURENTLY PROCESSING LOCATION IS NFS SHARED) ###
			request_in=os.listdir(script_path_in)
			for request in request_in:
			
				# Load configuration file if exists in current request and override server settings. Otherwise, move to the next request
				if os.path.exists(os.path.join(script_path_in,request,conf_file_name)):
					conf_in=load_conf(os.path.join(script_path_in,request,conf_file_name))
					if conf_in['docker_rep']:
						docker_rep=conf_in['docker_rep']
					if conf_in['docker_img']:
						docker_img=conf_in['docker_img']
					else:
						f_log.write('Error: No Docker image specified by end-user. Please, select one from '+str(docker_img_set))
						continue
					if docker_img_set and ('any' in docker_img_set or docker_img in docker_img_set):	# Check if end-user specified docker image exist in allowed images by institution
						pass
					else:
						f_log.write('Error: Docker image specified by end-user cannot be used\n')
						continue
					if conf_in['ser_check_thr']:
						ser_check_thr=conf_in['ser_check_thr']
				else:
					f_log.write("Error: Configuration does not exsit for "+request+" at "+str(time.time())+"\n")
					continue
			
				# Validate all input files and folders exist before processing. If not all input files and folder exist, move to next request
				if not check_input_files(os.path.join(script_path_in,request),conf_in['total_inputs']):
					f_log.write("Error: Some or all inputs files (folders) are missing for "+request+" at "+str(time.time())+"\n")
					continue
			
				# Now, request can be processed
				# Create 'results' folder (if not already exists) to keep output files. Otherwise, create a 'results' folder with new ID
				if os.path.exists(os.path.join(os.path.join(script_path_in,request),req_res_path_per_request)):
					req_res_path_per_request=req_res_path_per_request+"_"+str(uuid.uuid1())
				os.mkdir(os.path.join(os.path.join(script_path_in,request),req_res_path_per_request))	# To keep only required result files to be further processed or transfered.
			
				for f in conf_in['main_scripts']:
					service_name=os.path.splitext(os.path.split(f)[1])[0]
					docker_cmd=conf_in['docker_cmd_eng']+" "+f
					
					############ PRECAUTION: REMOVE DOCKER SERVICE IF ALREADY EXISTS ###########
					try:
						client.services.get(service_name).remove()
					except:
						pass
			
					############ BUILD THE NEW SERVICE ################
					#os.chmod(os.path.join(script_path_in,request),0777)	# Just a precaution for the following docker tasks
					script_processed=os.path.join(script_path_in,request)
					script_finished=os.path.join(script_path_out,request)
					script_failed=os.path.join(script_path_failed,request)
					#FIXME: docker service should be created by python docker module
					cmd="docker service create --name "+service_name+" --replicas "+docker_rep+" --restart-condition=on-failure --mount type=bind,source="+os.path.join(script_path_in,request)+",destination="+container_dir+" --mount type=bind,source="+data_dir+",destination="+conf_in['data_dir_container']+" --mount type=bind,source="+climate_dir+",destination="+climate_dir_container+" -w "+work_dir+" --env MY_TASK_ID={{.Task.Name}} --env PYTHONPATH="+climate_dir_container+" --env SCRIPTFILE="+f+" "+docker_img+" "+docker_cmd
					f_log.write(repr(time.time())+":"+cmd+"\n")	# Log the command
					try:
						os.system(cmd)
					except:
						f_log.write("Error occurred while launching service "+service_name+": "+ str(sys.exc_info())+"\n")
			
					########### CLEAN ONLY AFTER MAKING SURE OUTPUT IS SENT TO USER ##############
					if check_docker_service_complete(client,service_name,int(docker_rep),int(ser_check_thr)):
						# MOVE FINISHED SERVICE TO SUCCESSFUL REQUESTS PATH
						f_log.write("FINISHED at "+repr(time.time())+"\n\n")
						shutil.move(script_processed,script_finished)
						# COPY REQUIRED RESULT FILES FOR FURTHER PROCESSING OR TRANSFER
						for f_res in conf_in['result_files']:
							shutil.copy(os.path.join(script_finished,f_res),os.path.join(script_finished,req_res_path_per_request))
							# IF S3 IS ENABLED, THEN TRANSFER REQUIRED RESULT FILES TO S3 BUCKET
							if conf_in['s3_transfer'] and conf_in['s3_buc']:	  # s3_transfer is True and s3_buc has some value
								import boto3
								s3 = boto3.resource('s3')
								data = open(os.path.join(script_finished,f_res), 'rb')
								key_obj=conf_in['userid']+"/"+conf_in['s3_loc_under_userid']+"/"+f_res
								s3.Bucket(conf_in['s3_buc']).put_object(Key=key_obj, Body=data)		# In this script, we do not need AWS credentials, as this EC2 instance has the proper S3 rule
					else:
						shutil.move(script_processed,script_failed)
						f_log.write("FAILED at "+repr(time.time())+"\n")
					# DELTE DOCKER SERVICE
					try:
						client.services.get(service_name).remove()
					except:
						pass
		else:
			print('Error: Specified set '+set+' does not exist')
	except:
		print('Error occurred during running VIFI for set: '+set)
		print(sys.exc_info())
	finally:
		if f_log:
			f_log.close()
		
def vifi_run_f(set:str,conf_f:str)->None:
	''' VIFI request analysis and processing procedure for a specific set
	@param set: A specific set to run (i.e., receive and process requests)
	@type set: str
	@param conf_f: Input configuration file path (currently in YAML). conf_f preceeds @conf_in
	@type conf_f: str  
	@param conf_in: Configuration
	@type conf_in: dict  
	'''
	
	try:
		if os.path.isfile(conf_f):	# Check the existence of the configuration file
			with open(conf_f,'r') as f:
				conf=yaml.load(f)

			vifi_run(set, conf)
		else:
			print('Error: Could not find required configuration file')
	except:
		print('Error occurred during running VIFI for set: '+set)
		print(sys.exc_info())
	
if __name__ == '__main__':
	conf_f='vifi_config.yml'		# VIFI configuration file
	conf=loadVIFIConf(conf_f)		# Initialize VIIF configuration (i.e., directory structure for different sets (i.e., (sub)workflows))
	vifi_run(conf=conf,set='SHBE')		# Run VIFI analysis (to receive and process requests) for the specified set
	
