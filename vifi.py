'''
Created on Mar 29, 2018

@author: Mohammed Elshambakey
@contact: shambakey1@gmail.com
'''

import yaml, time, os, sys, shutil, json, uuid, requests, docker
import docker.models
from typing import List
from builtins import str, int
from genericpath import isfile

class vifi(object):
	'''
	VIFI class containing different methods for VIFI administrators to load configurations, initialize VIFI Nodes, 
	and process incoming requests
	'''


	def __init__(self,vifi_conf_f:str=None):
		'''
		VIFI Constructor
		@param vifi_conf_f: Path to VIFI configuration file
		@type vifi_conf: str  
		'''
		
		self.vifi_conf_f=''	# Path to VIFI configuration file for current VIFI instance
		self.vifi_conf={}	# VIFI configuration dictionary for current VIFI instance
		self.ser_list=[]	# List of created services by current VIFI Node
		
		if vifi_conf_f and os.path.isfile(vifi_conf_f):
			self.loadVIFIConf(vifi_conf_f)
			
			# Initialize containerization technology if any
			
		else:
			print("Error: No VIFI configuration file has been passed to this instance")
			sys.exit()
		
	def load_conf(self,infile:str)->dict:
		''' Loads user configuration file. "infile" is in JSON format
		@param infile: Path and name of the user input JSON configuration file
		@type infile: str  
		@return: User configuration file as JSON object
		@rtype: dict
		'''
	
		try:
			if infile and os.path.isfile(infile):
				with open(infile, 'r') as f:
					return yaml.load(f)
			else:
				print('Error: No user configuration file is specified')
		except Exception as e:
			print('Error occurred when opening user input configuration file:')
			if hasattr(e, 'message'):
				print(e.message)
			else:
				print(e)
	
	def checkInputFiles(self,in_file_root_loc:str,conf_in_total:dict)->bool:
		'''Checks if all user input files and directories exist. Returns true if all exists
		@param in_file_root_loc: Root path location of the user request folder
		@type in_file_root_loc: str
		@param conf_in_total: Dictionary of required input files/directories to execute user request
		@type conf_in_total: dict  
		'''
	
		try:
			for key,val in conf_in_total:
				if val=='f' and not os.path.isfile(os.path.join(in_file_root_loc,key)):	# Check file
					print('Error: Could not find user required input file '+os.path.join(in_file_root_loc,key))
					return False
				elif val=='d' and not os.path.isdir(os.path.join(in_file_root_loc,key)):
					print('Error: Could not find user required input directory '+os.path.join(in_file_root_loc,key))
					return False
				elif not os.path.exists(os.path.join(in_file_root_loc,key)):
					print('Error: Could not find user required input file/directory '+os.path.join(in_file_root_loc,key))
					return False
				
			return True
		except Exception as e:
			print('Error: checking user input files and folders:')
			if hasattr(e, 'message'):
				print(e.message)
			else:
				print(e)
	
	def getPromMetricsNames(self,prom_path:str,uname:str,upass:str,fname:str,fname_path:str)->List[str]:
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
	
	def getMetricsNames(self,metrics_f:str)-> List[str]:
		''' Read metrics names from JSON file. Useful when only a subset of metrics are required
		@param metrics_f: Path and name of JSON file containing metrics names
		@type metrics_f: str
		@return: List of metrics
		@rtype: List[str]
		'''
		
		with open(metrics_f, 'r') as f:
			return json.load(f)
	
	def getMetricsValues(self,m:List[str], start_t:float,end_t:float,prom_path:str,step:int,uname:str,upass:str,\
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
	
	def descVIFI(self):
		''' Prints general description about current VIFI instance '''
		
		if self.vifi_conf:
			print(str(self.vifi_conf))
		else:
			print('Current VIFI instance has no configuration')
	
	def loadVIFIConf(self,conf_f:str=None)->None:
		''' Load VIFI configuration for VIFI Node and make any necessary initialization for (sub)workflows
		@param conf_f: VIFI configuration file name (in YAML)
		@type conf_f: str 
		'''
		
		try:
			if conf_f and os.path.isfile(conf_f):	# Check the existence of the general VIFI configuration file
				self.vifi_conf_f=conf_f
				with open(conf_f,'r') as f:
					self.vifi_conf=yaml.load(f)
			else:
				if not self.vifi_conf:
					print('Error: could not find VIFI general configuration')
					sys.exit()
				
			# Info for root request directory
			root_script_path=self.vifi_conf['domains']['root_script_path']['name']	# Root directory for different domains requests
			root_script_path_mode=self.vifi_conf['domains']['root_script_path']['mode']	# Mode of requests root directory
			root_script_path_exist=self.vifi_conf['domains']['root_script_path']['exist_ok']	# If true, use already existing folder if one exists
			#FIXME: the following instruction should be used with the proper 'mode' configuration
			#os.makedirs(root_script_path,mode=root_script_path_mode,exist_ok=root_script_path_exist)	# Create requests root directory if not exists
			os.makedirs(root_script_path,exist_ok=root_script_path_exist)	# Create requests root directory if not exists
			
			# Default info for request structure within each domain 
			request_path_in=self.vifi_conf['domains']['script_path_in']['name']	# Path to receive requests within each domain
			request_path_in_mode=self.vifi_conf['domains']['script_path_in']['mode']	# Mode for received requests folder
			request_path_in_exist=self.vifi_conf['domains']['script_path_in']['exist_ok']	# If true, use already existing folder if one exists
			
			request_path_out=self.vifi_conf['domains']['script_path_out']['name']	# Path to output results within each domain
			request_path_out_mode=self.vifi_conf['domains']['script_path_out']['mode']	# Mode for output results folder
			request_path_out_exist=self.vifi_conf['domains']['script_path_out']['exist_ok']	# If true, use already existing folder if one exists
			
			request_path_failed=self.vifi_conf['domains']['script_path_failed']['name']	# Path to failed results within each domain
			request_path_failed_mode=self.vifi_conf['domains']['script_path_failed']['mode']	# Mode for failed results folder
			request_path_failed_exist=self.vifi_conf['domains']['script_path_failed']['exist_ok']	# If true, use already existing folder if one exists
			
			log_path=self.vifi_conf['domains']['log_path']['name']	# Path to logs within each domain
			log_path_mode=self.vifi_conf['domains']['log_path']['mode']	# Mode for logs folder
			log_path_exist=self.vifi_conf['domains']['log_path']['exist_ok']	# If true, use already existing folder if one exists
			
			#req_res_path_per_request=self.vifi_conf['domains']['req_res_path_per_request']['name']	# Path to intermediate results folder within each domain
			#req_res_path_per_request_mode=self.vifi_conf['domains']['req_res_path_per_request']['mode']	# Mode for logs folder
			#req_res_path_per_request_exist=self.vifi_conf['domains']['req_res_path_per_request']['exist_ok']	# If true, use already existing folder if one exists
			
			for d in self.vifi_conf['domains']['sets']:	# Create a sub-directory for each domain under the requests root directory
				#FIXME: the following commented instruction should be used whith the proper 'mode' configuration
				#os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name']),mode=conf['domains']['sets'][d]['mode'],exist_ok=conf['domains']['sets'][d]['exist_ok'])
				#os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],request_path_in),mode=request_path_in_mode,exist_ok=request_path_in_exist)
				#os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],request_path_out),mode=request_path_out_mode,exist_ok=request_path_out_exist)
				#os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],request_path_failed),mode=request_path_failed_mode,exist_ok=request_path_failed_exist)
				#os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],log_path),mode=log_path_mode,exist_ok=log_path_exist)
				#os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],req_res_path_per_request),mode=req_res_path_per_request_mode,exist_ok=req_res_path_per_request_exist)
				os.makedirs(os.path.join(root_script_path,self.vifi_conf['domains']['sets'][d]['name']),exist_ok=self.vifi_conf['domains']['sets'][d]['exist_ok'])
				os.makedirs(os.path.join(root_script_path,self.vifi_conf['domains']['sets'][d]['name'],request_path_in),exist_ok=request_path_in_exist)
				os.makedirs(os.path.join(root_script_path,self.vifi_conf['domains']['sets'][d]['name'],request_path_out),exist_ok=request_path_out_exist)
				os.makedirs(os.path.join(root_script_path,self.vifi_conf['domains']['sets'][d]['name'],request_path_failed),exist_ok=request_path_failed_exist)
				os.makedirs(os.path.join(root_script_path,self.vifi_conf['domains']['sets'][d]['name'],log_path),exist_ok=log_path_exist)
				#os.makedirs(os.path.join(root_script_path,self.vifi_conf['domains']['sets'][d]['name'],req_res_path_per_request),exist_ok=req_res_path_per_request_exist)	

		except Exception as e:
			print('Error occurred during loading VIFI configuration file:')
			if hasattr(e, 'message'):
				print(e.message)
			else:
				print(e)	
			
	def checkServiceComplete(self,client:docker.client.DockerClient,service_id:str,task_num_in:int,ttl:int=300)->bool:
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
	
	def checkServiceImage(self,docker_img_set:dict,user_img:str)-> str:
		''' Check if all user required services images are allowed by VIFI Node and return required image, or None if user required image cannot be verified by VIFI Node
		@param docker_img_set: Set of allowed images to use as specified by VIFI node
		@type docker_img_set: dict
		@param user_img: User required service image
		@type user_img: str
		@return: Required image or None if user's required image cannot be vierified by VIFI Node
		@rtype: str      
		'''
	
		if (user_img and 'any' in [x.lower() for x in docker_img_set.keys()]) or user_img in docker_img_set.keys():	# Use end-user specified container image if VIFI node allows any container image, or user selected one of the allowed images by VIFI node
			return user_img
		else:
			return None
	
	def setServiceNumber(self,docker_rep:str,user_rep:int)->int:
		''' Specify number of deployed tasks for user's request according to VIFI Node specifications and user's requirements
		@param docker_rep: Number of service tasks as specified by VIFI Node. If 'any', then VIFI Node allows any number of service tasks
		@type docker_rep: str
		@param  user_rep: Number of service tasks as required by user
		@type user_rep: int
		@return: Number of service tasks
		@rtype: int  
		'''
		def_rep=1	# Default number of service tasks
		if str(docker_rep).lower()=='any':	# VIFI Node allows any number of service tasks
			if user_rep:
				return user_rep
			else:
				return def_rep	# Default number of service tasks if user does not specify specific number of tasks
		else:
			if user_rep and user_rep<int(docker_rep):
				return user_rep	# Return required number of service tasks as it is allowed by VIFI Node
			else:
				return int(docker_rep)	# User required number of tasks exceeds allowed number by VIFI Node. Thus, reduce number of tasks to that allowed by VIFI Node
	
	def setServiceThreshold(self,ser_check_thr:str,user_thr:int)->int:
		''' Specify time threshold (or ttl) to check completeness of user's required service(s)
		@param ser_check_thr: Service check threshold (i.e., ttl) as specified by VIFI Node. If 'any', then VIFI Node allows infinite time to check service completeness
		@type ser_check_thr: str
		@param user_thr: Service check threshold (i.e., ttl) as required by user
		@type user_thr: int
		@return: Service check threshold (ttl)
		@rtype: int    
		'''
		
		def_ttl=300	# Default ttl
		if str(ser_check_thr).lower()=='any':
			if user_thr:
				return user_thr
			else:
				return def_ttl
		else:
			if user_thr and user_thr<int(ser_check_thr):
				return user_thr	# User specified threshold does not exceed maximum allowed threshold by VIFI Node
			else:
				return int(ser_check_thr)	# Return maximum allowed threshold by VIFI Node as user requires more than what is allowed
			
	def createUserService(self,client:docker.client.DockerClient,service_name:str,docker_rep:int,script_path_in:str,request:str,container_dir:str,\
						data_dir:dict,user_data_dir:dict,work_dir:str,script:str,docker_img:str,docker_cmd:str,ttl,
						user_args:List[str]=[],user_envs:List[str]=None,user_mnts:List[str]=None)->docker.models.services.Service:
		''' Create request service with required configurations (e.g., required mounts, environment variables, command, 
		arguments ... etc). Currently, service is created as docker service
		@param client: Client connection to docker enginer
		@type client: docker.client.DockerClient
		@param service_name: Required service name
		@type service_name: str
		@param docker_rep: Number of service tasks
		@type docker_rep: int
		@param script_path_in: Parent path for user's request
		@type script_path_in: str
		@param request: Directory name of user's request
		@type request: str
		@param container_dir: Container directory
		@type container_dir: str
		@param data_dir: Information dictionary of available data on current VIFI Node
		@type data_dir: dict
		@param user_data_dir: User specified mapping between required data directories and data paths inside created service tasks
		@type user_data_dir: dict
		@param work_dir: Working directory inside created service tasks
		@type work_dir: str
		@param script: User script to run within created service tasks
		@type script: str
		@param docker_img: Required service image (Currently, docker image)
		@type docker_img: str
		@param docker_cmd: User's command to run within created service tasks (e.g., python)
		@type docker_cmd: str
		@param user_args: User's arguments passed to @docker_cmd. Default is empty list
		@type user_args: List[str]
		@param ttl: Threshold time of the service (i.e., the time by which the service should have completed). It is recorded as one of the environment variables of the service
		@type ttl: int  
		@param user_envs: User list of environment variables for the created service tasks
		@type user_envs: List[str]
		@param user_mnts: User list of required mounts inside created service tasks
		@type user_mnts: List[str]
		@return: Required service
		@rtype: docker.models.services.Service    
		'''
		
		envs=['MY_TASK_ID={{.Task.Name}}','SCRIPTFILE='+script,'ttl='+ttl]	# Initialize list of environment variables
		if user_envs:	# Append user environment variables if any
			envs.extend(user_envs)
		
		# Mount the user request folder to the specified container_dir if any
		if container_dir:
			mnts=[os.path.join(script_path_in,request)+":"+container_dir]	# Initialize list of mounts for user's request
		else:
			mnts=[]
			
		# Mount the data directories
		for x in user_data_dir.keys():	# mount data physical path at VIFI Node to user specified paths
			mnts.append(data_dir[x]['path']+":"+user_data_dir[x])
			
		# Append any additional user mounts (which should be in the form source:target:options) relative to the user request directory 
		if user_mnts:
			for x in user_mnts:
				if x[0]=='/':	# User mount should be relative to the user request directory. Thus, any 'source' should not start with '/'
					x=x[1:]
				x=os.path.join(script_path_in,request,x)
				mnts.append(x)
			
		# Now, create the required (docker) service, and return it
		return client.services.create(name=service_name,mode={'Replicated':{'Replicas':docker_rep}},restart_policy=\
							{'condition':'on-failure'},mounts=mnts,workdir=work_dir,env=envs,image=docker_img,\
							command=docker_cmd+' '+script,args=user_args)
		
		
	def checkSerDep(self,client:docker.client.DockerClient,ser_name:str,user_conf:dict)->bool:
		''' Check if all preceding services are satisfied (i.e., completed) before running current service.
		@param client: Client connection to Docker
		@type client: :docker.client.DockerClient 
		@param ser_name: Service name to check its dependency
		@type ser_name: str  
		@param user_conf: User configurations
		@type user_conf: dict  
		@return: True if input service dependencies are satisfied. Otherwise, False
		@rtype: bool  
		'''
		
		#TODO: Currently, this method returns True if each previous service is completed. In the future, more sophisticated behavior may be needed
		
		# Get list of preceding services that should complete before current service
		dep_servs=user_conf['services'][ser_name]['dependencies']['ser']
		
		# Check satisfaction of each service if any (i.e., each service should reach the desired state)
		if dep_servs:
			for ser in dep_servs:
				# First, check service existence
				if not client.services.get(ser):
					return False
				
				# Check if service is complete. Note that we do not have to wait for the previous service ttl to check
				# completeness because the previous service should have already completed. Thus, the ttl is passed as 0
				if not self.checkServiceComplete(client, ser, ser.attrs['Spec']['Mode']['Replicated']['Replicas'],0):
					return False
		
		return True
	
	def checkFnDep(self,user_conf:dict)->bool:
		''' Check if precedence constraints, defined in terms of functions, are satisfied
		@param user_conf: User configuration file
		@type user_conf: dict
		@return: True if precedence functions are satisfied. Otherwise, False
		@rtype: bool 
		'''
		
		#TODO: Currently, this method alawys returns True. In the future, more sophosticated check should be done
		return True
	
	def checkDataOpt(self,conf:dict, user_conf:dict)->bool:
		''' Check if all user required data can be mounted with user required options (e.g., mount data in write mode)
		@param conf: VIFI Node configuration dictionary for the specific set
		@type conf: dict  
		@param user_conf: User configuration file
		@type user_conf: dict  
		@return: True if user required data options can be satisfied
		@rtype: bool 
		'''
		
		#FIXME: Currently, we assume all user required data options can be satisfied. Later, this method may need to communicate with security layer
		return True
	
	def checkSerName(self,ser:str,client:docker.client.DockerClient)->str:
		''' Check if required service name is unique.
		@todo: Currently, if service name is not unique, the new service is revoked. In the future, a new name should be assigned to the service  
		@param ser: Service name to check its uniqueness
		@type ser: str
		@param client: Client connection to docker engine
		@type client: docker.client.DockerClient
		@return: Unique service name, or None if impossible to get a unique service name
		@rtype: str
		'''
		
		if client.services.get(ser):
			return None
		else:
			return ser
		
	def getSerName(self)->str:
		''' Generate a unique VIFI request (i.e., service) name all over VIFI system
		'''
		
		#TODO: There can be better ways to generate unique service name
		return str(uuid.uuid4())
	
	def delService(self,client:docker.client.DockerClient,ser_name:str,term_time:str)->None:
		''' Deletes specified service after specified termination time
		@param client: Docker client connection
		@type client: docker.client.DockerClient 
		@param ser_name: Service name 
		@type ser_name: str
		@param term_time: Termination time after which the specified service is removed
		@type term_time: str  
		'''
		
		#TODO: Currently, this function either directly removes the service, or leaves it indefinitely. In the future, there should be a separate thread (such that other requests are not delayed until the specified service is removed) to monitor services and remove them according to specified termination time.
		if term_time != 'inf':
			client.services.get(ser_name).remove()
	
	def s3Transfer(self,user_s3_conf:dict,data_path:str)->None:
		''' Transfer files to S3 bucket
		@param user_s3_conf: User configurations related to S3 bucket
		@type user_s3_conf: dict  
		@param data_path: Path of files to be transfered
		@type data_path: str  
		''' 		
		
		import boto3
		s3 = boto3.resource('s3')
		for path,dir,f_res in os.walk(data_path):
			data = open(os.path.join(path,dir,f_res), 'rb')
			key_obj=user_s3_conf['path']+"/"+f_res
			s3.Bucket(user_s3_conf['bucket']).put_object(Key=key_obj, Body=data)		# In this script, we do not need AWS credentials, as this EC2 instance has the proper S3 rule
			
	def vifi_run(self,set:str,conf:dict=None,set_fn:str=None)->None:
		''' VIFI request analysis and processing procedure for a specific set. The specified set may request a \
		specific function to modify/override default processing behavior. The default behavior of 'vifi_run' is to \
		keep incoming requests at specific locations, then run them as containerized applications in container \
		cluster (e.g., Docker swarm)
		@param set: A specific set (i.e., (sub)set) to run (i.e., receive and process requests)
		@type set: str
		@param conf: VIFI Node configuration
		@type conf_in: dict
		@param set_fn: Specific function for specified set to change the default processing behavior
		@type set_fn: str
		'''
	
		f_log=''	# Variable of log file
		
		try:
			
			# Make sure that VIFI server configuration exist 
			if not conf:
				if self.vifi_conf:
					conf=self.vifi_conf
				else:
					print('Error: No VIFI server configuration exists')
					sys.exit()
					
			# Check if required set exists
			if set in conf['domains']['sets']:
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
					docker_img_set=conf['domains']['sets'][set]['docker']['docker_img']	# Set of allowed docker images
					docker_rep=conf['domains']['sets'][set]['docker']['docker_rep']	# Maximum number of tasks that can be run by any user for this specific set
					ser_check_thr=conf['domains']['sets'][set]['docker']['ttl'] # Default ttl for each (Docker) service
					client=docker.from_env()
				else:
					print('Error: No containerization technique and/or stand alone service is specified to run (sub)workflow '+set)
					return
					
				### LOOP THROUGH REQUESTS AND PROCESS THEM (CURENTLY PROCESSING LOCATION IS NFS SHARED) ###
				request_in=os.listdir(script_path_in)
				for request in request_in:
					
					# Initialize path parameters for current request
					script_processed=os.path.join(script_path_in,request)
					script_finished=os.path.join(script_path_out,request)
					script_failed=os.path.join(script_path_failed,request)
				
					# Check and load user configuration file if exists in current request and override server settings. Otherwise, move to the next request
					if os.path.exists(os.path.join(script_path_in,request,conf_file_name)):
						conf_in=self.load_conf(os.path.join(script_path_in,request,conf_file_name))
					else:
						f_log.write("Error: Configuration does not exist for "+request+" at "+str(time.time())+"\n")
						#TODO: if this situation continues, then move to failed
						continue
					
					# Traverse all services of the current request
					for ser in conf_in['services']:
						
						# Check required service name uniqueness (Just a precaution, as the request name- which should also be the service name- must be unique when the user made the request)
						service_name=self.checkSerName(ser)
						if not service_name:
							f_log.write("Error: Another service (i.e., request) with the same name, "+request+", exists at "+str(time.time())+"\n")
							#TODO: move to failed. In the future, another service name should be generated if desired
							continue
						
						# Check that user required images are allowed by VIFI Node
						docker_img=self.checkServiceImage(conf['domains']['sets'][set]['docker']['docker_img'],conf_in['services'][ser]['image'])
						if not docker_img:
							f_log.write('Error: Wrong container images specified by end-user. Please, select one from '+str(conf['domains']['sets'][set]['docker']['docker_img'])+" for request "+request+" at "+str(time.time())+"\n")
							#TODO: move to failed
							continue
						
						# Check all user required data can be mounted in user required mode (e.g., write mode)
						if not self.checkDataOpt(conf,conf_in):
							f_log.write('Error: Wrong data mounting options specified by end-user for request '+request+" at "+str(time.time())+"\n")
							#TODO: move to failed
							continue
						
						# Check all files are satisfied for current service. Otherwise, move to the next service
						if not self.checkInputFiles(os.path.join(script_path_in,request),conf_in['services'][ser]['dependencies']['files']):
							f_log.write("Error: Some or all required files are missed for "+request+" at "+str(time.time())+"\n")
							#TODO: if this situation continues, then move to failed
							continue
						
						# Check all preceding services are complete, or the preceding service(s) reached the required status, before running the current service
						if not self.checkSerDep(service_name,conf_in):
							f_log.write("Error: Some or all preceding services are missed for "+request+" at "+str(time.time())+"\n")
							#TODO: if this situation continues, then move to failed
							continue
						
						# Check if other precedence conditions (e.g., functions) are satisfied before running current service. Otherwise, move to next request
						if not self.checkFnDep(conf_in):
							f_log.write("Error: Some or all precedence functions are missed for "+request+" at "+str(time.time())+"\n")
							#TODO: if this situation continues, then move to failed
							continue
						
						# Check available task number for current service (VIFI Node can limit concurrent number of running tasks for one service)
						docker_rep=self.setServiceNumber(docker_rep, conf_in['services'][ser]['tasks'])	# set number of service tasks to allowed number
						if docker_rep!=conf_in['services'][ser]['tasks']:
							f_log.write("Warning: Number of tasks for request "+str(request)+" will be "+str(docker_rep)+" at "+str(time.time())+"\n")
							
						# Check time threshold to check service completeness
						ser_check_thr=self.setServiceThreshold(ser_check_thr, conf_in['services'][ser]['ser_check_thr'])	# set ttl to allowed value
						if ser_check_thr!=conf_in['services'][ser]['ser_check_thr']:
							f_log.write("Warning: Service check threshold for request "+str(request)+" will be "+str(ser_check_thr)+" at "+str(time.time())+"\n")
						
						# Create a 'results' folder in current request (if not already exists) to keep output files. Otherwise, create a 'results' folder with new ID
						req_res_path_per_request=conf['domains']['req_res_path_per_request']['name']
						if os.path.exists(os.path.join(os.path.join(script_path_in,request),req_res_path_per_request)):
							req_res_path_per_request=req_res_path_per_request+"_"+str(uuid.uuid1())
						os.mkdir(os.path.join(os.path.join(script_path_in,request),req_res_path_per_request))	# To keep only required result files to be further processed or transfered.
						
						# Create the required containerized user service, add service name to internal list of services, and log the created service
						#TOOO: Currently, the created service is appended to an internal list of service. In the future, we may need to keep track of more parameters related to the created service (e.g., user name, request path, ... etc)
						try:
							self.createUserService(client=client, service_name=service_name, docker_rep=docker_rep, \
											script_path_in=script_path_in, request=request, \
											container_dir=conf_in['services'][ser]['container_dir'], data_dir=data_dir, \
											user_data_dir=conf_in['services'][ser]['data'], work_dir=conf_in['services'][ser]['work_dir'], f=conf_in['services'][ser]['script'], \
											docker_img=docker_img, docker_cmd=conf_in['services'][ser]['cmd_eng'], \
											user_args=conf_in['services'][ser]['args'], user_envs=conf_in['services'][ser]['envs'], user_mnts=conf_in['services'][ser]['mnts'],ttl=ser_check_thr)
							self.ser_list.append(service_name)
							f_log.write(repr(time.time())+":"+str(client.services.get(service_name))+"\n")	# Log the command
						except Exception as e:
							f_log.write("Error: occurred while launching service "+service_name+": "+ str(sys.exc_info())+"\n")
							if hasattr(e, 'message'):
								print(e.message)
							else:
								print(e)
								
						# Check completeness of created service to transfer results (if required) and to end service
						if self.checkServiceComplete(client,service_name,int(docker_rep),int(ser_check_thr)):
							# Log completeness time
							f_log.write("FINISHED at "+repr(time.time())+"\n\n")
							
							# Move finished service to successful requests path
							shutil.move(script_processed,script_finished)
							
							# Copy required results to specified destinations
							for f_res in conf_in['services'][ser]['results']:
								# Local copy of required final results (Just in case they are needed in the future)
								shutil.copy(os.path.join(script_finished,f_res),os.path.join(script_finished,req_res_path_per_request))
								
							# IF S3 IS ENABLED, THEN TRANSFER REQUIRED RESULT FILES TO S3 BUCKET
							if conf_in['services'][ser]['s3']['transfer'] and conf_in['services'][ser]['s3']['bucket']:	  # s3_transfer is True and s3_buc has some value
								self.s3Transfer(conf_in['services'][ser]['s3'], os.path.join(script_finished,req_res_path_per_request))
								f_log.write("Transfered to S3 bucket at "+repr(time.time())+"\n")
						else:
							shutil.move(script_processed,script_failed)
							f_log.write("FAILED at "+repr(time.time())+"\n")
						
						# Delete service, if required, to release resource
						try:
							self.delService(client, service_name, str(conf['domains']['sets'][set]['terminate']))
						except:
							f_log.write("Error: failed to delete service "+service_name+" at "+repr(time.time())+"\n")
							continue
			else:
				print('Error: Specified set '+set+' does not exist')
		except Exception as e:
			print('Error occurred during running VIFI for set: '+set)
			#print(sys.exc_info())
			if hasattr(e, 'message'):
				print(e.message)
			else:
				print(e)
		finally:
			if f_log:
				f_log.close()
			
		
	if __name__ == '__main__':
		print("########## THIS IS VIFI SERVER ##########")
		print(vifi.__doc__)
		
	
		