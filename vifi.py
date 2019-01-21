'''
Created on Mar 29, 2018

@author: Mohammed Elshambakey
@contact: shambakey1@gmail.com
'''

import yaml, time, os, sys, shutil, json, uuid, requests, traceback, select, multiprocessing
import nipyapi
from nipyapi import canvas, templates
from nipyapi.nifi.apis.remote_process_groups_api import RemoteProcessGroupsApi	
from nipyapi.nifi.apis.connections_api import ConnectionsApi
import pandas as pd
import docker.models
from typing import List
from zipfile import ZipFile
from builtins import str, int
from multiprocessing import Process
from multiprocessing.managers import BaseManager
from _io import TextIOWrapper
import argparse

class vifi():
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
		
		# Initialize VIFI instance parameters
		self.vifi_conf_f=''	# Path to VIFI configuration file for current VIFI instance
		self.vifi_conf={}	# VIFI configuration dictionary for current VIFI instance
		self.req_list={}	# Dictionary of created requests by current VIFI Node
		self.nifi_tr_res_flows=[]	# List of deployed NIFI templates to transfer results between NIFI remote sites
		self.stop=False	# If TRUE, the current VIFI instance stops

			
		# Load VIFI configuration file
		try:
			if vifi_conf_f and os.path.isfile(vifi_conf_f):
				self.loadVIFIConf(vifi_conf_f)
			else:
				print("Error: No VIFI configuration file has been passed to this instance")
				sys.exit()
		except:
			result='Error: "VIFI constructor" function has error(vifi_server): '
			print(result)
			traceback.print_exc()
	
	def end(self):
		''' Stop current VIFI instance
		'''
		
		self.stop=True
	
	def dump_conf(self,conf:dict,outfile:str,flog:TextIOWrapper=None)-> None:
		''' Dumps configuration dictionary into the required YAML file
		@param conf: Configuration dictionary to be dumped
		@type conf: dict 
		@param outfile: Path and name of the user output YAML configuration file
		@type outfile: str  
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		'''
		
		try:
			if not conf:
				print('Error: No configuration is specified to dump')
			elif not outfile:
				print('Error: No file specified to dump the configuration')
			else:
				with open(outfile,'w') as f:
					yaml.dump(conf,f,default_flow_style=False)
					
		except:
			result='Error: "dump_conf" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
		
	def load_conf(self,infile:str,flog:TextIOWrapper=None)->dict:
		''' Loads user configuration file. "infile" is in JSON format
		@param infile: Path and name of the user input YAML configuration file
		@type infile: str  
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		@return: User configuration file as JSON object
		@rtype: dict
		'''
	
		try:
			if infile and os.path.isfile(infile):
				with open(infile, 'r') as f:
					return yaml.load(f)
			else:
				print('Error: No user configuration file is specified')
		except:
			result='Error: "load_conf" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def checkInputFiles(self,in_file_root_loc:str,conf_in_total:dict,flog:TextIOWrapper=None)->bool:
		'''Checks if all user input files and directories exist. Returns true if all exists
		@param in_file_root_loc: Root path location of the user request folder
		@type in_file_root_loc: str
		@param conf_in_total: Dictionary of required input files/directories to execute user request
		@type conf_in_total: dict  
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		@return: True if all user input files/directories exist. False otherwise
		@rtype: bool  
		'''
	
		try:
			for key,val in conf_in_total.items():
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
		except:
			result='Error: "CheckInputFiles" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def getPromMetricsNames(self,prom_path:str,uname:str,upass:str,fname:str,fname_path:str,flog:TextIOWrapper=None)->List[str]:
		''' Retrive Prometheus metrics names and write them to output file if required in JSON structure 
		@param prom_path: Prometheus API url
		@type prom_path: str  
		@param uname: Prometheus username
		@type uname: str
		@param upass: Prometheus password
		@type upass: str
		@param fname: File to record metrics names
		@type fname: str
		@param fname_path: Path to store @fname
		@type fname_path: str 
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)  
		@return: List of metrics names
		@rtype: List[str]	  
		'''
		
		try:
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
		except:
			result='Error: "getPromMetricsNames" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def getMetricsNames(self,metrics_f:str,flog:TextIOWrapper=None)-> List[str]:
		''' Read metrics names from JSON file. Useful when only a subset of metrics are required
		@param metrics_f: Path and name of JSON file containing metrics names
		@type metrics_f: str
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		@return: List of metrics
		@rtype: List[str]
		'''
		
		try:
			with open(metrics_f, 'r') as f:
				return json.load(f)
		except:
			result='Error: "getMetricsNames" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def getMetricsValues(self,m:List[str], start_t:float,end_t:float,prom_path:str,step:int,uname:str,upass:str,\
						write_to_file:bool,fname:str,fname_path:str,flog:TextIOWrapper=None)->dict:
		''' Get specified metric values for specified duration if start and end times of duration are specified. If either \
		start or end times are not specified, then query is done only at the time instance that is specified by either of \
		them.
		@param m: Metrics names
		@type m: List[str] 
		@param prom_path: Prometheus API url 
		@type prom_path: str
		@param start_t: Start time to collect metric'vifi_server time series values (Unix Time Stamp). Defaults to current time. If not specified, the query is done at a single time instance specified by @end_t. At least @start_t and/or @end_t should be specified.
		@type start_t: float 
		@param end_t: End time to collect metric'vifi_server time series values (Unix Time Stamp). Defaults to current time. If not specified, the query is done at a single time instance specified by @start_t. At least @start_t and/or @end_t should be specified.
		@type end_t: float   
		@param step: Time step during query interval
		@type step: int
		@param uname: Prometheus username
		@type uname: str
		@param upass: Prometheus user password
		@type upass: str
		@param write_to_file: If set_i, then write output metric(vifi_server) values to specified file if one is specified by @fname under specified path given by @fname_path. If @fname is not specified, then create separate file for each metric.
		@type write_to_file: bool
		@param fname: File name to record output metric(vifi_server) values under specified path given by @fname_path. If not specified while @write_to_file is set_i, then a separate file is created for each metric.
		@type fname: str
		@param fname_path: Path of @fname. Defaults to current directory
		@type fname_path: str
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)   
		@return: Metric(vifi_server) values for the specified time interval at the specified steps, or at a specific time instance
		@rtype: dict
		'''
		#TODO: If start_t is not specified, then start query from the earliest possible timedate. But this depeneds on how long Prometheus stores data series, and the incremental step
		
		try:
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
		except:
			result='Error: "getMetricsValues" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def descVIFI(self,flog:TextIOWrapper=None):
		''' Prints general description about current VIFI instance '''
		
		try:
			if self.vifi_conf:
				print(str(self.vifi_conf))
			else:
				print('Current VIFI instance has no configuration')
		except:
			result='Error: "descVIFI" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()	
	
	def loadVIFIConf(self,conf_f:str=None,flog:TextIOWrapper=None)->None:
		''' Load VIFI configuration for VIFI Node and make any necessary initialization for (sub)workflows
		@param conf_f: VIFI configuration file name (in YAML)
		@type conf_f: str
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)  
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

		except:
			result='Error: "loadVIFIConf" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()	
			
	def checkServiceComplete(self,client:docker.client.DockerClient,service_name:str,task_num_in:int,ttl:int=3600,\
							flog:TextIOWrapper=None)->bool:
		''' Check if specified Docker service has finished currently or within specified time threshold
		@param client: Client connection to Docker Engine
		@type client: client connection
		@param service_id: Required Service ID whose status is to be checked
		@type service_id: str
		@param task_num: Number of tasks (i.e., replicas) within the service
		@type task_num: int
		@param ttl: Time threshold after which, the service is considered NOT complete
		@type ttl: int  
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		@return: True if all tasks of required service are complete. Otherwise, false
		@rtype: bool    
		'''
		
		### Checks if each task in task_num has completed
		try:
			while ttl:
				try:
					ser=client.services.get(service_name)
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
		except:
			result='Error: "checkServiceComplete" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def checkServiceImage(self,docker_img_set:dict,user_img:str,flog:TextIOWrapper=None)-> str:
		''' Check if all user required services images are allowed by VIFI Node and return required image, or None if user required image cannot be verified by VIFI Node
		@param docker_img_set: Set of allowed images to use as specified by VIFI node
		@type docker_img_set: dict
		@param user_img: User required service image
		@type user_img: str
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper 
		@return: Required image or None if user'vifi_server required image cannot be vierified by VIFI Node
		@rtype: str      
		'''
	
		try:
			if (user_img and 'any' in [x.lower() for x in docker_img_set.keys()]) or user_img in docker_img_set.keys():	# Use end-user specified container image if VIFI node allows any container image, or user selected one of the allowed images by VIFI node
				return user_img
			else:
				return None
		except:
			result='Error: "checkServiceImage" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def setServiceNumber(self,docker_rep:str,user_rep:int=None,flog:TextIOWrapper=None)->int:
		''' Specify number of deployed tasks for user'vifi_server request according to VIFI Node specifications and user'vifi_server requirements
		@param docker_rep: Number of service tasks as specified by VIFI Node. If 'any', then VIFI Node allows any number of service tasks
		@type docker_rep: str
		@param  user_rep: Number of service tasks as required by user
		@type user_rep: int
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		@return: Number of service tasks
		@rtype: int  
		'''
		
		try:
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
		except:
			result='Error: "setServiceNumber" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def setServiceThreshold(self,ser_check_thr:str,user_thr:int=None,flog:TextIOWrapper=None)->int:
		''' Specify time threshold (or ttl) to check completeness of user'vifi_server required service(vifi_server)
		@param ser_check_thr: Service check threshold (i.e., ttl) as specified by VIFI Node. If 'any', then VIFI Node allows infinite time to check service completeness
		@type ser_check_thr: str
		@param user_thr: Service check threshold (i.e., ttl) as required by user
		@type user_thr: int
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		@return: Service check threshold (ttl)
		@rtype: int    
		'''
		
		try:
			def_ttl=3600	# Default ttl
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
		except:
			result='Error: "setServiceThreshold" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
			
	def createUserService(self,client:docker.client.DockerClient,service_name:str,docker_rep:int,script_path_in:str,request:str,container_dir:str,\
						data_dir:dict,user_data_dir:dict,work_dir:str,script:str,docker_img:str,docker_cmd:str,ttl,
						user_args:List[str]=[],user_envs:List[str]=None,user_mnts:List[str]=None,user=None, groups=None,flog:TextIOWrapper=None)->docker.models.services.Service:
		''' Create request service with required configurations (e.g., required mounts, environment variables, command, 
		arguments ... etc). Currently, service is created as docker service
		@param client: Client connection to docker enginer
		@type client: docker.client.DockerClient
		@param service_name: Required service name
		@type service_name: str
		@param docker_rep: Number of service tasks
		@type docker_rep: int
		@param script_path_in: Parent path for user'vifi_server request
		@type script_path_in: str
		@param request: Directory name of user'vifi_server request
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
		@param docker_cmd: User'vifi_server command to run within created service tasks (e.g., python)
		@type docker_cmd: str
		@param user_args: User'vifi_server arguments passed to @docker_cmd. Default is empty list
		@type user_args: List[str]
		@param ttl: Threshold time of the service (i.e., the time by which the service should have completed). It is recorded as one of the environment variables of the service
		@type ttl: int  
		@param user_envs: User list of environment variables for the created service tasks
		@type user_envs: List[str]
		@param user_mnts: User list of required mounts inside created service tasks
		@type user_mnts: List[str]
		@param user: The user to run the container
		@type user: str
		@param groups: The groups to run the container
		@type groups: List[str]  
		@param flog: Log file object to record raised events
		@type flog: TextIOWrapper (file object)
		@return: Required service
		@rtype: docker.models.services.Service    
		'''
		try:
			envs=['MY_TASK_ID={{.Task.Name}}','SCRIPTFILE='+script,'ttl='+str(ttl)]	# Initialize list of environment variables
			if user_envs:	# Append user environment variables if any
				envs.extend(user_envs)
			
			# Mount the user request folder to the specified container_dir if any. Otherwise, the user request
			# folder is mapped to the root directory in the container
			if not container_dir:
				container_dir=os.path.abspath(os.sep)
			mnts=[os.path.join(script_path_in,request)+":"+container_dir+":rw"]	# Initialize list of mounts for user'vifi_server request
				
			# Mount the data directories
			for x in user_data_dir.keys():	# mount data physical path at VIFI Node to user specified paths
				mnts.append(data_dir[x]['path']+":"+user_data_dir[x]['container_data_path'])
				
			# Append any additional user mounts (which should be in the form source:target:options) relative to the user request directory 
			if user_mnts:
				for x in user_mnts:
					if x[0]=='/':	# User mount should be relative to the user request directory. Thus, any 'source' should not start with '/'
						x=x[1:]
					x=os.path.join(script_path_in,request,x)
					mnts.append(x)
			
			# Determine the user and group(s) used to run the container services if none is provided
			if not user:
				user=str(os.getuid())
			if not groups:
				groups=[str(os.getgid())]
				
			# Now, create the required (docker) service, and return it
			return client.services.create(name=service_name,mode={'Replicated':{'Replicas':docker_rep}},restart_policy=\
								{'condition':'on-failure'},mounts=mnts,workdir=work_dir,env=envs,image=docker_img,\
								command=docker_cmd+' '+script,args=user_args, user=user, groups=groups)
		except:
			result='Error: "createUserService" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
		
		
	def checkSerDep_ORG(self,client:docker.client.DockerClient,ser_name:str,user_conf:dict,flog:TextIOWrapper=None)->bool:
		''' (DEPRECATED) Check if all preceding services are satisfied (i.e., completed) before running current service.
		@deprecated: Use @checkSerDep function instead
		@param client: Client connection to Docker
		@type client: :docker.client.DockerClient 
		@param ser_name: Service name to check its dependency
		@type ser_name: str  
		@param user_conf: User configurations
		@type user_conf: dict  
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)  
		@return: True if input service dependencies are satisfied. Otherwise, False
		@rtype: bool  
		'''
		
		#TODO: Currently, this method returns True if each previous service is completed. In the future, more sophisticated behavior may be needed
		
		try:
			# Get list of preceding services that should complete before current service
			dep_servs=user_conf['services'][ser_name]['dependencies']['ser']
			
			# Check satisfaction of each service if any (i.e., each service should reach the desired state)
			if dep_servs:
				for ser in dep_servs:
					# First, check service existence
					if ser not in [x.name for x in client.services.list()]:
						return False
					
					# Check if service is complete. Note that we do not have to wait for the previous service ttl to check
					# completeness because the previous service should have already completed. Thus, the ttl is passed as 0
					if not self.checkServiceComplete(client, ser, ser.attrs['Spec']['Mode']['Replicated']['Replicas'],0):
						return False
			
			return True
		except:
			result='Error: "checkSerDep" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def checkSerDep(self,servs:dict,ser_name:str,user_conf:dict,flog:TextIOWrapper=None)->bool:
		''' Check if all preceding services are satisfied (i.e., completed) before running current service.
		@param servs: Dictionary of services of current request
		@type servs: dict 
		@param ser_name: Service name to check its dependency
		@type ser_name: str  
		@param user_conf: User configurations
		@type user_conf: dict  
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)  
		@return: True if input service dependencies are satisfied. Otherwise, False
		@rtype: bool  
		'''
		
		#TODO: Currently, this method returns True if each previous service is completed. In the future, more sophisticated behavior may be needed
		
		try:
			# Get list of preceding services that should complete before current service
			dep_servs=[]
			for i in user_conf['services']:	# The loop is needed in case of investigating dependencies for iterative service. In current VIFI implementation, an iterative service is composed of the basic service name, plus a UUID
				if i in ser_name:
					dep_servs=user_conf['services'][i]['dependencies']['ser']
					break
			
			# Check satisfaction of each service if any (i.e., each service should reach the desired state)
			if dep_servs:
				for ser in dep_servs:
					# Check service existence
					if ser in servs and servs[ser]['cur_iter']<servs[ser]['max_rep']:
						return False
					
			return True
		
		except:
			result='Error: "checkSerDep" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def checkFnDep(self,user_conf:dict,flog:TextIOWrapper=None)->bool:
		''' Check if precedence constraints, defined in terms of functions, are satisfied
		@param user_conf: User configuration file
		@type user_conf: dict
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		@return: True if precedence functions are satisfied. Otherwise, False
		@rtype: bool 
		'''
		
		#TODO: Currently, this method alawys returns True. In the future, more sophosticated check should be done
		try:
			return True
		except:
			result='Error: "checkFnDep" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def checkDataOpt(self,conf:dict, user_conf:dict,flog:TextIOWrapper=None)->bool:
		''' Check if all user required data can be mounted with user required options (e.g., mount data in write mode)
		@param conf: VIFI Node configuration dictionary for the specific set_i
		@type conf: dict  
		@param user_conf: User configuration file
		@type user_conf: dict  
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		@return: True if user required data options can be satisfied
		@rtype: bool 
		'''
		
		#FIXME: Currently, we assume all user required data options can be satisfied. Later, this method may need to communicate with security layer
		try:
			return True
		except:
			result='Error: "checkDataOpt" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
				
	
	def checkSerName(self,ser:str='',iter_no:int=0,client:docker.client.DockerClient=None,flog:TextIOWrapper=None)->str:
		''' Check if required service name is unique. In case of iterative service, a modified service name is returned.
		@todo: Currently, if service name is not unique, the new service is revoked. In the future, a new name should be assigned to the service  
		@param ser: Service name to check its uniqueness
		@type ser: str
		@param iter_no: The current iteration number of current iterative service. Defaults to 1 which means the service is either not iterative or in the last iteration
		@type iter_no: int  
		@param client: Client connection to docker engine
		@type client: docker.client.DockerClient
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		@return: Unique service name, or None if impossible to get a unique service name
		@rtype: str
		'''
		
		try:
			# Check if service name already exists
			ser=self.getSerName(ser, iter_no, flog)
			for x in client.services.list():
				if ser in x.name:
					return None
				else:
					return ser
			

		except:
			result='Error: "checkSerName" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
		
	def getSerName(self,ser_name:str='',iter_no:int=0,flog:TextIOWrapper=None)->str:
		''' Generate a unique VIFI request (i.e., service) name all over VIFI system
		@param ser_name: Original service name. If given, this service name will be modified. Otherwise, a new name will be generated
		@type ser_name: str  
		@param iter_no: Current iteration number for iterative services. Defaults to 0
		@type iter_no: int   
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		@return: Unique service name
		@rtype: str 
		'''
		
		#TODO: There can be better ways to generate unique service name
		try:
			if iter_no:
				return ser_name+"_"+str(iter_no)
			else:
				return ser_name
		except:
			result='Error: "getSerName" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def delService(self,client:docker.client.DockerClient,ser_name:str,term_time:str,flog:TextIOWrapper=None)->None:
		''' Deletes specified service after specified termination time
		@param client: Docker client connection
		@type client: docker.client.DockerClient 
		@param ser_name: Service name 
		@type ser_name: str
		@param term_time: Termination time after which the specified service is removed
		@type term_time: str 
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)   
		'''
		
		#TODO: Currently, this function either directly removes the service, or leaves it indefinitely. In the future, there should be a separate thread (such that other requests are not delayed until the specified service is removed) to monitor services and remove them according to specified termination time.
		try:
			if term_time != 'inf':
				client.services.get(ser_name).remove()
		except:
			result='Error: "delService" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def nifiTransfer(self,user_nifi_conf:dict,data_path:str,pg_name:str,tr_res_temp_name:str='tr_res_temp', \
					flog:TextIOWrapper=None)->bool:
		''' Transfer required results as a compressed zip file using NIFI
		NOTE: Current implementation just creates the compressed file to be transfered by NIFI. Current implementation 
		does not transfer the file by itself. The transfer process is done by NIFI workflow design
		@param user_nifi_conf: User configurations related to NIFI
		@type user_nifi_conf: dict  
		@param data_path: Directory path of file to be transfered
		@type data_path: str 
		@param pg_name: NIFI Processor group name corresponding to required set
		@type pg_name: str 
		@param tr_res_temp_name: NIFI Transfer results template name. Defaults to 'tr_res_temp' template
		@type tr_res_temp_name: str 
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		@return: True to indicate success
		@rtype: bool
		'''
		
		try:

			# Copy the results directory to a user_name directory, under the results directory, if not already exists
			shutil.copytree(data_path, os.path.join(data_path,user_nifi_conf['archname']))
			
			# Compress the created user_name directory
			shutil.make_archive(os.path.join(data_path,user_nifi_conf['archname']), 'zip', data_path, user_nifi_conf['archname'])
			
			# Remove the created user_name directory
			shutil.rmtree(os.path.join(data_path,user_nifi_conf['archname']), ignore_errors=True)
			
			# Retrieve processor group for the specified set
			set_pg=canvas.get_process_group(pg_name)
			
			# Retrieve transfer results template
			tr_res_temp=templates.get_template_by_name(tr_res_temp_name)
			
			# Deploy the transfer results template and keep a reference for it
			tr_res_flow=templates.deploy_template(set_pg.id,tr_res_temp.id)
			self.nifi_tr_res_flows.append(tr_res_flow)
			
			# A reference to 'get result file' processor
			tr_res_get_results=tr_res_flow.flow.processors[0]
			
			# A reference to the 'remote site' to transfer results
			tr_res_remote=tr_res_flow.flow.remote_process_groups[0]
			
			# A reference to the connection between 'get results file' processor and the remote process group
			tr_res_conn=tr_res_flow.flow.connections[0]
			
			# Create an instance of RemoteProcessGroupsApi to update the remote process group
			rpg_api=RemoteProcessGroupsApi()
			
			# Specify the target URI for the remote site and update the remote site
			tr_res_remote.component.target_uri=user_nifi_conf['target_uri']
			tr_res_remote.component.target_uris=user_nifi_conf['target_uri']
			rpg_api.update_remote_process_group(tr_res_remote.id, tr_res_remote)
			
			# Update the reference to the modified remote process group
			req_remote_port=None
			while tr_res_remote.status.target_uri!=user_nifi_conf['target_uri'] or \
			user_nifi_conf['target_remote_input_port'] not in [k.name for k in tr_res_remote.component.contents.input_ports]:
				tr_res_remote=canvas.get_remote_process_group(tr_res_remote.id)
			
			# Create an instance of the ConnectionsApi
			conn_api=ConnectionsApi()
			
			# Retrieve information about the required input port of the remote process group. This step should be done after updating the target_uri(vifi_server) of the remote process group
			while not req_remote_port:
				for k in tr_res_remote.component.contents.input_ports:
					if k.name==user_nifi_conf['target_remote_input_port']:
						req_remote_port=k
						break
			
			# Modify the connection to the remote process group to reflect the correct input port
			#tr_res_conn=conn_api.get_connection(tr_res_conn.id)
			tr_res_conn.destination_id=req_remote_port.id
			tr_res_conn.component.destination.id=req_remote_port.id
			
			# Update the connection to the required input port of the remote process group
			conn_api.update_connection(tr_res_conn.id, tr_res_conn)
			
			# Update the reference to the connection to the remote process group
			while tr_res_conn.status.destination_name!=req_remote_port.name or \
			tr_res_conn.status.destination_id!=req_remote_port.id:
			#tr_res_conn.status.aggregate_snapshot.destination_name!=req_remote_port.name or \
			#tr_res_conn.status.aggregate_snapshot.destination_id!=req_remote_port.id:
				tr_res_conn=conn_api.get_connection(tr_res_conn.id)
			
			# Modify the 'get results' processor to indicate the path and the name of the compressed results file
			tr_res_get_results=canvas.get_processor(tr_res_get_results.id,'id')
			tr_res_get_results.component.config.properties['Input Directory']=data_path
			tr_res_get_results.component.config.properties['File Filter']=user_nifi_conf['archname']+'.zip'
			
			# Update the 'get results' processor with the new attributes
			canvas.update_processor(tr_res_get_results, tr_res_get_results.component.config)
			
			# Update the reference to the 'get results' processor
			while tr_res_get_results.component.config.properties['Input Directory']!=data_path or \
			tr_res_get_results.component.config.properties['File Filter']!=user_nifi_conf['archname']+'.zip':
				tr_res_get_results=canvas.get_processor(tr_res_get_results.id,'id')
						
			# Start the 'get results' processor to start transferring results file
			canvas.schedule_processor(tr_res_get_results, True)
			while canvas.get_processor(tr_res_get_results.component.name).revision.version==tr_res_get_results.revision.version:
				# TODO: I think there should be a more restrict condition than checking version to ensure the processor has run 
				pass
			
			# Enable transmission of the remote process group to finish transfer of the results file
			while tr_res_remote.status.target_uri!=user_nifi_conf['target_uri'] or \
			user_nifi_conf['target_remote_input_port'] not in [k.name for k in tr_res_remote.component.contents.input_ports]:
				tr_res_remote=canvas.get_remote_process_group(tr_res_remote.id)	# This step is to ensure the remote port still exists because the remote site may experience some problems
			tr_res_remote_stat={'revision':tr_res_remote.revision,'state':'TRANSMITTING','disconnectedNodeAcknowledged':True}
			rpg_api.update_remote_process_group_run_status(tr_res_remote.id,tr_res_remote_stat)
			while tr_res_remote.status.transmission_status!='Transmitting':
				tr_res_remote=canvas.get_remote_process_group(tr_res_remote.id)
			
			# Check that the results file has been transmitted
			while tr_res_remote.status.aggregate_snapshot.flow_files_sent==0:
				tr_res_remote=canvas.get_remote_process_group(tr_res_remote.id)
			
			### TIME TO REMOVE THE DEPLOYED TRANSFER REUSULTS TEMPLATE ###
			
			# Disable transmission of the remote process group and update reference to the remote process group
			tr_res_remote_stat={'revision':tr_res_remote.revision,'state':'STOPPED','disconnectedNodeAcknowledged':True}
			rpg_api.update_remote_process_group_run_status(tr_res_remote.id,tr_res_remote_stat)
			while tr_res_remote.status.transmission_status!='NotTransmitting':
				tr_res_remote=canvas.get_remote_process_group(tr_res_remote.id)
			
			# Stop the 'get results' processor and update the reference to the 'get results' processor
			canvas.schedule_processor(tr_res_get_results, False)
			
			# Delete the 'get results' processor and the associated connection to the remote process group
			canvas.delete_processor(tr_res_get_results,force=True)
			
			# Delete the remote process group
			rpg_api.remove_remote_process_group(tr_res_remote.id,version=tr_res_remote.revision.version)
			
			# Retun True to indicate transfer success
			return True
			
		except:
			result='Error: "nifiTransfer" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
				
			# Return False to indicate transfer failure
			return False
		
	def s3Transfer(self,user_s3_conf:dict,data_path:str,flog:TextIOWrapper=None)->None:
		''' Transfer files to S3 bucket
		@param user_s3_conf: User configurations related to S3 bucket
		@type user_s3_conf: dict  
		@param data_path: Path of files to be transfered
		@type data_path: str  
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		''' 		
		
		import boto3
		
		try:
			s3 = boto3.resource('s3')
			for path,dir,f_res in os.walk(data_path):
				for f in f_res:
					data = open(os.path.join(path,f), 'rb')
					key_obj=user_s3_conf['path']+"/"+f
					s3.Bucket(user_s3_conf['bucket']).put_object(Key=key_obj, Body=data)		# In this script, we do not need AWS credentials, as this EC2 instance has the proper S3 rule
		except:
			result='Error: "s3Transfer" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
				
	def changePermissionsRecursive(self,path:str, mode=0o777,flog:TextIOWrapper=None)->None:
		''' Changes permissions of files and folders recursively under specified path
		@see https://www.tutorialspoint.com/How-to-change-the-permission-of-a-directory-using-Python
		@param path: Top path to change permissions
		@type path: str
		@param mode: Permissions mode to set_i
		@type mode: Oct    
		'''
		
		try:
			for root, dirs, files in os.walk(path,topdown=False):
				for dir_in in [os.path.join(root,d) for d in dirs]:
					if os.stat(dir_in).st_uid==os.getuid() and os.stat(dir_in).st_gid==os.getgid():
						os.chmod(dir_in,mode)
					
				for file in [os.path.join(root,f) for f in files]:
					if os.stat(file).st_uid==os.getuid() and os.stat(file).st_gid==os.getgid():
						os.chmod(file,mode)
			
			if os.stat(root).st_uid==os.getuid() and os.stat(root).st_gid==os.getgid():
				os.chmod(root,mode)	
					
		except:
			result='changePermissionsRecursive" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def unpackCompressedRequests(self,conf:dict=None,sets:List[str]=None,flog:TextIOWrapper=None)->None:
		''' Unpack any compressed requests under specified set_i(vifi_server) (i.e., (sub)workflow(vifi_server))
		@param conf: VIFI configuration file
		@type conf: dict
		@param sets: List of required sets (i.e., (sub)workflow(vifi_server)) to unpack incoming requests. Defaults to all sets if None is specified
		@type sets: List[str]  
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		'''
		
		try:
			# Either load input VIFI configuration file, or load internal VIFI configuration file
			if not conf:
				if not self.vifi_conf:
					print('Error: No VIFI configuration exist')
					sys.exit()
				else:
					conf=self.vifi_conf
					
			# If input sets are not specified, then load all sets in VIFI configuration if any
			if not sets:
				sets=conf['domains']['sets']
				
			# Traverse through all sets
			for dset in sets:
				# Determine path to compressed requests under specified set_i
				comp_path=os.path.join(conf['domains']['root_script_path']['name'],conf['domains']['sets'][dset]['name'],\
									conf['domains']['script_path_in']['name'])
				
				# List all requests under current set_i
				reqs=os.listdir(comp_path)
				
				# Unpack compressed files only, then remove the compressed file after extraction
				for req in reqs:
					# Unpack file according to file extension
					if req.endswith('.zip'):
						
						# Get the request name without extension
						req_name=os.path.splitext(os.path.basename(req))[0]
						
						# Get the path to finished requests
						script_path_out=os.path.join(conf['domains']['root_script_path']['name'],conf['domains']['sets'][dset]['name'],\
										conf['domains']['script_path_out']['name'])
						
						# If a directory exists in the 'finished' with the same name, then move it to working directory. Then extract the compressed file to update the contents of the retrieved directory
						if os.path.exists(os.path.join(script_path_out,req_name)):
							shutil.move(os.path.join(script_path_out,req_name), os.path.join(comp_path,req_name))
						
						# Now, extract the compressed request
						with ZipFile(os.path.join(comp_path,req)) as f:
							f.extractall(comp_path)
					
						# Remove compressed file after extraction
						os.remove(os.path.join(comp_path,req))
						
						# Change permissions for uncompressed folder (Currently, permissions are changed to 777 to allow writing by docker services into created folders)
						self.changePermissionsRecursive(os.path.join(comp_path,req).split('.zip')[0])
		except:
			result='Error: "unpackCompressedRequests" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def unpackCompressedRequestsLoop(self,conf:dict=None,sets:List[str]=None,flog:TextIOWrapper=None)->None:
		''' Perform unpackCompressedRequests in a loop until STOP condition of current VIFI instance is True
		@param conf: VIFI configuration file
		@type conf: dict
		@param sets: List of required sets (i.e., (sub)workflow(vifi_server)) to unpack incoming requests. Defaults to all sets if None is specified
		@type sets: List[str]  
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		'''
		try:
			
			# Either load input VIFI configuration file, or load internal VIFI configuration file
			if not conf:
				if not self.vifi_conf:
					print('Error: No VIFI configuration exist')
					sys.exit()
				else:
					conf=self.vifi_conf
						
			while not self.stop:
				self.unpackCompressedRequests(conf, sets, flog)
				time.sleep(conf['domains']['unpack_int'])
		
		except:
			result='Error: "unpackCompressedRequestsLoop" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
				
	def reqLog(self,req_log_path:str,req_log:dict,req:str='general_log')-> None:
		''' Write request logs under specified path.
		TODO: Currently, request log is written as YAML file
		@param req_log_path: Path to keep request log
		@type req_log_path: str
		@param req_log: Request log
		@type req_log: dict
		@param req: Request name. Defaults to 'general_log' if not specified
		@type req: str   
		'''
		
		# Create log directory if not exists
		os.makedirs(req_log_path,exist_ok=True)
		
		# Write request log to created log file. Log file is created if not already exists
		if not (req.endswith('.yml') or req.endswith('.yaml')):
			req=req+".yml"
		with open(os.path.join(req_log_path,req),'w') as f:
			yaml.dump(req_log,f)
			
	def reqsAnalysis(self,req_paths:List[str],req_analysis_f:str,req_analysis_path:str=None,prom_conf:dict=None,\
					metrics_values_path:str=None,metrics_values_f:str=None,flog:TextIOWrapper=None)->pd.DataFrame:
		''' Analyze requests logs
		@note: Despite this function can be moved outside the class. I preferred to leave it in the class just in case it may be needed in the future for scheduling and load balancing
		@note: This function depends on the YAML structure of requests logs
		@note: Current implementation makes a simple analysis, and collection of Prometheus metrics
		@param req_paths: Paths to requests to analyze 
		@type req_paths: List[str] 
		@param req_analysis_f: Optional file to keep requests analysis results
		@type req_analysis_f: str
		@param req_analysis_path: Path to store generated analysis files
		@type req_analysis_path: str 
		@param prom_conf: VIFI Node configuration for Prometheus 
		@type prom_conf: dict
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		@return: Analysis results
		@rtype: pandas.DataFrame  
		'''
		
		import ntpath
		
		try:
			# Initialize required variables
			dt=[]	# List to hold all analysis record of all requests
			cnt=0	# Counter to index analysis records
			
			# Record Prometheus metrics if required
			if prom_conf:
				# Determine file path containing metrics names
				metrics_names=os.path.join(prom_conf['metrics_names_path'],\
									prom_conf['metrics_names_f'])
				
				# Retrieve required metrics names from file if exists. Otherwise, create file
				if os.path.isfile(metrics_names) and os.path.getsize(metrics_names)>0:
					metrics=self.getMetricsNames(metrics_names, flog)
				else:
					os.makedirs(prom_conf['metrics_names_path'],exist_ok=True)
					metrics=self.getPromMetricsNames(prom_path=prom_conf['prometheus_url'],\
													uname=prom_conf['uname'],\
													upass=prom_conf['upass'],\
													fname=prom_conf['metrics_names_f'],\
													fname_path=prom_conf['metrics_names_path'],flog=flog)
				
				# Determine file name and path to record collected Prometheus metrics if required
				if not metrics_values_f:
					metrics_values_f=prom_conf['metrics_values_f']
				
				if not metrics_values_path:
					metrics_values_path=prom_conf['metrics_values_path']
			
			# Traverse through all required requests paths
			for reqf in req_paths:
				# Initialize prometheus variables
				with open(reqf,'r') as x:
					req=yaml.load(x)
					for ser in req['services']:
						d=pd.DataFrame(data={'request':reqf,'service':[ser],'start':[float(req['services'][ser]['start'])],\
											'end':[float(req['services'][ser]['end'])],'cmp_time':\
											[float(req['services'][ser]['end'])-float(req['services'][ser]['start'])],\
											'no_tasks':[int(req['services'][ser]['tasks'])]},index=[cnt])
						dt.append(d)	# Append current record to collected analysis results
						cnt=cnt+1	# Increment record index
				
					# Record Prometheus metrics if allowed by VIFI node
					if prom_conf:
						# Determine first time to record metrics as start time of first service in request
						metric_start=min([req['services'][ser]['start'] for ser in req['services']])
						
						# Determine last time to record metrics as the end time of last service in request 
						metric_end=max([req['services'][ser]['end'] for ser in req['services']])
						
						# If no file is given to record Prometheus metrics, then make file name that contains Prometheus metrics values. File name consists of request name, start time of first service, end time of last service 
						if not metrics_values_f:
							metrics_values_fname=ntpath.basename(reqf)+'_'+str(metric_start)+'_'+str(metric_end)
										
						# Record Prometheus metrics in created Prometheus file
						self.getMetricsValues(m=metrics, start_t=metric_start, end_t=metric_end, prom_path=prom_conf['prometheus_url'],\
								step=prom_conf['query_step'],uname=prom_conf['uname'],upass=prom_conf['upass'],\
								write_to_file=prom_conf['write_metrics'], fname=metrics_values_fname, \
								fname_path=metrics_values_path, flog=flog)
			
			# Join all analysis records together		
			df=pd.concat(dt)
			
			# Reorder collected records for a better view
			df=df[['request','service','no_tasks','start','end','cmp_time']]
			
			# Create final analysis file, or open an existing one if desired
			if req_analysis_f:
				if req_analysis_path and os.path.isdir(req_analysis_path):
					req_analysis_f=os.path.join(req_analysis_path,req_analysis_f)
				with open(req_analysis_f,'w') as f:
					df.to_csv(f,index=False)
				
			
			# Return collected analysis records
			return df
		
		except:
			result='Error: "reqAnalysis" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def reqsDirAnalysis(self,req_log_dir:str,req_analysis_path:str=None,req_analysis_f:str=None,prom_conf:dict=None,\
					metrics_values_path:str=None,metrics_values_f:str=None,flog:TextIOWrapper=None)->pd.DataFrame:
		''' Analyzes all request logs that exist in a specific directory
		@note: Despite this function can be moved outside the class. I preferred to leave it in the class just in case it may be needed in the future for scheduling and load balancing
		@param req_log_dir: Directory containing request logs
		@type req_log_dir: str
		@param req_analysis_path: Path to store resulting analysis files
		@type req_analysis_path: str
		@param req_analysis_f: Optional file to keep requests analysis results
		@type req_analysis_f: str
		@param prom_conf: Prometheues configuration
		@type prom_conf: dict 
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		@return: Analysis results
		@rtype: pandas.DataFrame  
		'''
		
		try:
			# Check directory path is valid
			if os.path.isdir(req_log_dir):
				
				# Initialize empty list to hold requests' logs
				req_logs=[]
				
				# Collect all requests logs
				for path,dir,f_res in os.walk(req_log_dir):
					for f in f_res:
						req_logs.append(os.path.join(path,f))
						
				# Pass collected logs to @reqsAnalysis
				return self.reqsAnalysis(req_paths=req_logs,req_analysis_f=req_analysis_f,\
										req_analysis_path=req_analysis_path,prom_conf=prom_conf,\
					metrics_values_path=metrics_values_path,metrics_values_f=metrics_values_f,flog=flog)
			else:
				# Direcory path is not valid
				print('Error: directory path is not valid')
				return None
		
		except:
			result='Error: "reqDirAnalysis" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
				
			return None
		
	def serIterate(self,iter_conf:dict=None,ser_it_no:int=0,flog:TextIOWrapper=None)-> bool:
		''' Determine if it is required to repeat the service again. If no configuration is given, then the service is not repeated any more.
		NOTE: Current implementation just checks that maximum number of iterations has not been exceeded. Future implementation may encounter other conditions.
		@param iter_conf: Service configuration for the iterations
		@type iter_conf: dict
		@param ser_it_no: Current service iteration number. Incremented each time the service runs
		@type: int
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		@return: True if service needs to be repeated. Otherwise, False
		@rtype: bool
		'''
		
		try:
			if iter_conf:
				if ser_it_no<iter_conf['max_rep']:
					return True
			
			return False
		
		except:
			result='Error: "serIterate" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
				
			return None
	
	
	def getReqLastState(self,conf:dict=None,flog:TextIOWrapper=None)->dict:
		''' Retreive the last state of user's request. The request state includes:
		- The name of each service, the maximum iterations of the service, and the current iteration number of the service
		@param conf: User request configuration file
		@type conf: dict
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		@return: The request last state dictionary
		@rtype: dict  
		'''
		
		try:
			servs={}	# Initiate an empty dictionary for request's state
			
			# Iterate through services in request's configuration. Record only the unfinished services
			for ser in conf['services']:
				if conf['services'][ser]['iterative']['cur_iter']<conf['services'][ser]['iterative']['max_rep']:
					servs[ser]={}
					servs[ser]['max_rep']=conf['services'][ser]['iterative']['max_rep']
					servs[ser]['cur_iter']=conf['services'][ser]['iterative']['cur_iter']
			
			# Return request's state
			return servs
		
		except:
			result='Error: "getReqLastState" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
				
			return None
			
	def vifiRun(self,sets:List[str]=None,request_in:List[str]=None,conf:dict=None)->None:
		''' VIFI request analysis and processing procedure for list of sets (i.e., (sub)workflows). The default 
		processing behavior of 'vifiRun' is to keep incoming requests at specific locations, then run them as \
		containerized applications in container cluster (e.g., Docker swarm). The default processing behavior can \
		change if the set_i specifies another function to use in the configuration file
		@param sets: List of sets (i.e., (sub)workflows) to run (i.e., receive and process requests)
		@type sets: List[str]
		@param request_in: List of users' requests within specified @sets to be processed (i.e., path to request folder)
		@type request_in: List[str] 
		@param conf: VIFI Node configuration
		@type conf_in: dict 
		'''
	
		try:
			flog=''
				
			# Make sure that VIFI server configuration exist 
			if not conf:
				if self.vifi_conf:
					conf=self.vifi_conf
				else:
					print('Error: No VIFI server configuration exists')
					sys.exit()

			# Acquire all existing sets if none specified
			if not sets:
				sets=conf['domains']['sets']
			# Traverse through required sets
			for dset in sets:	
			# Check if required set_i exists
				if dset in conf['domains']['sets']:
					### INITIALIZE USER PARAMETERS (APPLICABLE FOR ANY USER) ###
					conf_file_name=conf['user_conf']['conf_file_name']
		
					### INITIALIZE REQUIRED PATH VARIABLES FOR SPECIFIED SET ###
					script_path_in=os.path.join(conf['domains']['root_script_path']['name'],conf['domains']['sets'][dset]['name'],\
										conf['domains']['script_path_in']['name'])
					script_path_out=os.path.join(conf['domains']['root_script_path']['name'],conf['domains']['sets'][dset]['name'],\
										conf['domains']['script_path_out']['name'])
					script_path_failed=os.path.join(conf['domains']['root_script_path']['name'],conf['domains']['sets'][dset]['name'],\
										conf['domains']['script_path_failed']['name'])
					log_path=os.path.join(conf['domains']['root_script_path']['name'],conf['domains']['sets'][dset]['name'],\
										conf['domains']['log_path']['name'])
					req_res_path_per_request=os.path.join(conf['domains']['root_script_path']['name'],conf['domains']['sets'][dset]['name'],conf['domains']['req_res_path_per_request']['name'])
					data_dir=conf['domains']['sets'][dset]['data_dir']
					
					### LOGGING PARAMETERS ###
					flog_path=os.path.join(log_path,"out.log")
					flog = open(flog_path, 'a')
					flog.write("Scheduled by VIFI Orchestrator for set_i "+dset+" at "+str(time.time())+"\n")
							
					### IF DOCKER IS USED FOR THIS SET, THEN INITIALIZE DEFAULT DOCKER PARAMETERS ###
					### SOME DOCKER PARAMETERS CAN BE OVERRIDEN BY END USER IF ALLOWED ###
					if 'docker' in conf['domains']['sets'][dset] and conf['domains']['sets'][dset]['docker']:
						docker_img_set=conf['domains']['sets'][dset]['docker']['docker_img']	# Set of allowed docker images
						docker_rep=conf['domains']['sets'][dset]['docker']['docker_rep']	# Maximum number of tasks that can be run by any user for this specific set_i
						ser_check_thr=conf['domains']['sets'][dset]['docker']['ttl'] # Default ttl for each (Docker) service
						docker_user=conf['domains']['sets'][dset]['docker']['user']		# User to run docker container
						docker_groups=conf['domains']['sets'][dset]['docker']['groups']		# List of groups to run docker container
						client=docker.from_env()
					else:
						print('Error: No containerization technique and/or stand alone service is specified to run (sub)workflow '+dset)
						return
					
					### IF NIFI IS ENABLED FOR THIS SET, THEN INITIALIZE NIFI HOST AND REGISTRY IF EXISTS ###
					if conf['domains']['sets'][dset]['nifi']['transfer']:
						nipyapi.config.nifi_config.host = conf['domains']['sets'][dset]['nifi']['host']
						if conf['domains']['sets'][dset]['nifi']['registry']:
							nipyapi.config.registry_config.host = conf['domains']['sets'][dset]['nifi']['registry']
					
					# Acquire all requests under current set_i if none provided
					if not request_in:
						request_in=os.listdir(script_path_in)
						
					### USE PROVIDED SET FUNCTION IF EXISTS ###
					set_fun=conf['domains']['sets'][dset]['set_function']
					if set_fun:
						#TODO: Currently, only default set_i behavior is used
						pass
					else:
						### LOOP THROUGH REQUESTS AND PROCESS THEM (CURENTLY PROCESSING LOCATION IS NFS SHARED) ###
						for request in request_in:
							
							# Initialize final services status to check status of all underlying services for current request
							final_req_stat=True	# True is a temporary value. It changes to False if any underlying service fails, or due to any other failure to process the request
							
							# Update the internal list of processed requests with 'status=start'
							self.req_list[request]={'status':'start','start':str(time.time()),'services':{}}
							
							# Initialize path parameters for current request
							script_processed=os.path.join(script_path_in,request)
							script_finished=os.path.join(script_path_out,request)
							script_failed=os.path.join(script_path_failed,request)
						
							# Check and load user configuration file if exists in current request and override server settings. Otherwise, move to the next request
							if os.path.exists(os.path.join(script_path_in,request,conf_file_name)):
								conf_in=self.load_conf(os.path.join(script_path_in,request,conf_file_name))
							else:
								flog.write("Error: Configuration does not exist for "+request+" at "+str(time.time())+"\n")
								#TODO: if this situation continues, then move to failed
								continue
							
							# Initiate a dictionary of services for current request. This set can be modified after reading the configuration file of current request (due to checkpointing, which is a future feature, some services may have already been finished)
							servs=self.getReqLastState(conf=conf_in)
							
							# Create a 'results' folder in current request (if not already exists) to keep output files.
							req_res_path_per_request=conf['domains']['req_res_path_per_request']['name']
							if not os.path.exists(os.path.join(os.path.join(script_path_in,request),req_res_path_per_request)):
								#req_res_path_per_request=req_res_path_per_request+"_"+str(uuid.uuid1())
								os.mkdir(os.path.join(os.path.join(script_path_in,request),req_res_path_per_request))	# To keep only required result files to be further processed or transfered.
							
							# Traverse all services of the current request
							for ser in conf_in['services']:
								# If current service already finished, then move to the next service
								if ser not in servs:
									continue
								
								# Set current service iteration
								ser_it=servs[ser]['cur_iter']
																
								# Initialize temporary service status to record status of created service (True if service succeeds)
								tmp_ser_stat=False
								
								# Check if the service still needs to iterate
								while self.serIterate(iter_conf=conf_in['services'][ser]['iterative'],ser_it_no=ser_it):
									
									# Check required service name uniqueness (Just a precaution, as the request name- which should also be the service name- must be unique when the user made the request)
									service_name=self.checkSerName(ser=ser,iter_no=ser_it,client=client)
									if not service_name:
										flog.write("Error: Another service with the same name, "+service_name+", exists at "+str(time.time())+"\n")
										#TODO: move to failed. In the future, another service name should be generated if desired
										break
									
									# Check that user required images are allowed by VIFI Node
									docker_img=self.checkServiceImage(conf['domains']['sets'][dset]['docker']['docker_img'],conf_in['services'][ser]['image'])
									if not docker_img:
										flog.write('Error: Wrong container images specified by end-user. Please, select one from '+str(conf['domains']['sets'][dset]['docker']['docker_img'])+" for request "+request+" at "+str(time.time())+"\n")
										#TODO: move to failed
										break
									
									# Check all user required data can be mounted in user required mode (e.g., write mode)
									if not self.checkDataOpt(conf,conf_in):
										flog.write('Error: Wrong data mounting options specified by end-user for request '+request+" at "+str(time.time())+"\n")
										#TODO: move to failed
										break
									
									# Check all files are satisfied for current service. Otherwise, move to the next service
									if not self.checkInputFiles(os.path.join(script_path_in,request),conf_in['services'][ser]['dependencies']['files']):
										flog.write("Error: Some or all required files are missed for "+request+" at "+str(time.time())+"\n")
										#TODO: if this situation continues, then move to failed
										continue
									
									# Check all preceding services are complete, or the preceding service(vifi_server) reached the required status, before running the current service
									if not self.checkSerDep(servs=servs, ser_name=service_name, user_conf=conf_in):
										flog.write("Error: Some or all preceding services are missed for "+request+" at "+str(time.time())+"\n")
										#TODO: if this situation continues, then move to failed
										continue
									
									# Check if other precedence conditions (e.g., functions) are satisfied before running current service. Otherwise, move to next request
									if not self.checkFnDep(conf_in):
										flog.write("Error: Some or all precedence functions are missed for "+request+" at "+str(time.time())+"\n")
										#TODO: if this situation continues, then move to failed
										continue
									
									# Check available task number for current service (VIFI Node can limit concurrent number of running tasks for one service)
									task_no=self.setServiceNumber(docker_rep=docker_rep, user_rep=conf_in['services'][ser]['tasks'])	# set_i number of service tasks to allowed number
									if task_no!=conf_in['services'][ser]['tasks']:
										flog.write("Warning: Number of tasks for service "+service_name+" in request "+str(request)+" will be "+str(task_no)+" at "+str(time.time())+"\n")
										
									# Check time threshold to check service completeness
									ser_ttl=self.setServiceThreshold(ser_check_thr, conf_in['services'][ser]['ser_check_thr'])	# set_i ttl to allowed value
									if ser_ttl!=conf_in['services'][ser]['ser_check_thr']:
										flog.write("Warning: Service check threshold for request "+str(request)+" will be "+str(ser_ttl)+" at "+str(time.time())+"\n")
									
									# Create the required containerized user service, add service name to internal list of services of current request, and log the created service
									#TOOO: Currently, the created service is appended to an internal list of service. In the future, we may need to keep track of more parameters related to the created service (e.g., user name, request path, ... etc)
									try:
										if self.createUserService(client=client, service_name=service_name, docker_rep=task_no, \
														script_path_in=script_path_in, request=request, \
														container_dir=conf_in['services'][ser]['container_dir'], data_dir=data_dir, \
														user_data_dir=conf_in['services'][ser]['data'], work_dir=conf_in['services'][ser]['work_dir'], script=conf_in['services'][ser]['script'], \
														docker_img=docker_img, docker_cmd=conf_in['services'][ser]['cmd_eng'], \
														user_args=conf_in['services'][ser]['args'], user_envs=conf_in['services'][ser]['envs'], user_mnts=conf_in['services'][ser]['mnts'],ttl=ser_ttl, \
														user=docker_user, groups=docker_groups):
											ser_start_time=time.time()	# Record service creation time
											self.req_list[request]['services'][service_name]={'tasks':task_no}
											self.req_list[request]['services'][service_name]['start']=ser_start_time
											flog.write(repr(ser_start_time)+":"+str(client.services.get(service_name))+"\n")	# Log the command
										else:
											flog.write("Error: Could not create service "+service_name+": \n")
											traceback.print_exc(file=flog)
										
									except:
										flog.write("Error: occurred while launching service "+service_name+": \n")
										traceback.print_exc(file=flog)
											
									# Check completeness of created service to transfer results (if required) and to end service
									if self.checkServiceComplete(client,service_name,int(task_no),int(ser_ttl)):
										# Log completeness time
										ser_end_time=time.time()
										self.req_list[request]['services'][service_name]['end']=ser_end_time
										flog.write("Finished service "+service_name+" for request "+request+" at "+repr(ser_end_time)+"\n\n")
										
										# Copy required results, if any, to specified destinations
										if conf_in['services'][ser]['results']:
											for f_res in conf_in['services'][ser]['results']:
												# Move required final results (Just in case they are needed in the future)
												if os.path.exists(os.path.join(script_processed,f_res)):
													shutil.move(os.path.join(script_processed,f_res), os.path.join(script_processed,req_res_path_per_request,f_res))
												else:
													flog.write("Failed to locally copy result "+os.path.join(script_processed,f_res)+" at "+repr(time.time())+"\n")
										
										# Update service status, request status, and request configuration file
										tmp_ser_stat=True
										servs[ser]['cur_iter']+=1
										conf_in['services'][ser]['iterative']['cur_iter']+=1
										self.dump_conf(conf_in, os.path.join(script_path_in,request,conf_file_name), flog)
										
										# Delete service, if required, to release resource
										try:
											# TODO: Deleted or finished services should be recorded (either in a local list/dict, or in the user configuration file). Thus, it will be known which services, or service iterations, have finished  
											self.delService(client, service_name, str(conf['domains']['sets'][dset]['terminate']))
										except:
											flog.write("Error: failed to delete service "+service_name+" at "+repr(time.time())+"\n")
											continue
											
										# IF S3 IS ENABLED, THEN TRANSFER REQUIRED RESULT FILES TO S3 BUCKET
										if conf_in['services'][ser]['s3']['transfer'] and conf_in['services'][ser]['s3']['bucket']:	  # s3_transfer is True and s3_buc has some value
											self.s3Transfer(conf_in['services'][ser]['s3'], os.path.join(script_processed,req_res_path_per_request))
											flog.write("Transfered to S3 bucket at "+repr(time.time())+"\n")
										
										# If NIFI is enabled, then transfer required results using NIFI 
										if conf_in['services'][ser]['nifi']['transfer']:
											if self.nifiTransfer(user_nifi_conf=conf_in['services'][ser]['nifi'], \
															data_path=os.path.join(script_processed,req_res_path_per_request), \
															pg_name=dset, \
															tr_res_temp_name='tr_res_temp'):
												# NIFI transfer succeeded 
												flog.write("Intermediate results transfer by NIFI succeeded at "+repr(time.time())+"\n")
											else:
												# NIFI transfer failed
												flog.write("Intermediate results transfer by NIFI failed at "+repr(time.time())+"\n")
												# TODO: should the user request be terminated? or just continue with future service(vifi_server) 
									
									else:
										# Service failed
										break	
									
									# Update service iteration number
									ser_it+=1
									
								if not tmp_ser_stat:
									#TODO: If current service fails, then abort whole request. This behavior may need modifications in the future
									self.req_list[request]['services'][service_name]={'end':'failed'}
									flog.write("Failed service "+service_name+" for request "+request+" at "+repr(time.time())+"\n\n")
									
								# Update request status according to current service status, and abort request if any service fails
								final_req_stat=final_req_stat and tmp_ser_stat
								if not final_req_stat:
									break
							
							# Record request end time and update internal request dictionary
							req_end_time=time.time()
							self.req_list[request]['end']=req_end_time
							
							# Move finished request to successful requests path, or to failed otherwise. Update internal requests dictionary accordingly
							if final_req_stat:
								shutil.move(script_processed,script_finished)
								self.req_list[request]['status']='success'
								flog.write("Request "+request+" finished at "+repr(req_end_time)+"\n")
								
								# Move final results to final destination
								if conf_in['fin_dest']['transfer']:
									
									# IF S3 IS ENABLED, THEN TRANSFER REQUIRED RESULT FILES TO S3 BUCKET
									if conf_in['fin_dest']['s3']['transfer'] and conf_in['fin_dest']['s3']['bucket']:	  # s3_transfer is True and s3_buc has some value
										self.s3Transfer(conf_in['fin_dest']['s3'], os.path.join(script_finished,req_res_path_per_request))
										flog.write("Transfered final results to S3 bucket at "+repr(time.time())+"\n")
									
									# If NIFI is enabled, then transfer required results using NIFI 
									if conf_in['fin_dest']['nifi']['transfer']:
										if self.nifiTransfer(user_nifi_conf=conf_in['fin_dest']['nifi']['transfer'], \
															data_path=os.path.join(script_finished,req_res_path_per_request), \
															pg_name=dset, \
															tr_res_temp_name='tr_res_temp'):
											# Wait for the transfer to be done
											flog.write("Final results transfer by NIFI succeeded at "+repr(time.time())+"\n")
										else:
											# Final results transfer by NIFI failed
											flog.write("Final results transfer by NIFI failed at "+repr(time.time())+"\n")
							else:
								shutil.move(script_processed,script_failed)
								self.req_list[request]['status']='fail'
								flog.write("Request "+request+" FAILED at "+repr(req_end_time)+"\n")
								
							# Write the request log
							self.reqLog(req_log_path=self.vifi_conf['req_log_path'], req_log=self.req_list[request],req=request+'_'+str(time.time()))
							
							# Clean the request log to save resource
							self.req_list.clear()
								
				else:
					print('Error: Specified set_i '+dset+' does not exist')
		except:
			result='Error: "vifiRun" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
		finally:
			if flog:
				flog.close()
	
	def vifiRunLoop(self,sets:List[str]=None,request_in:List[str]=None,conf:dict=None,flog:TextIOWrapper=None)-> None:
		''' Performs vifiRun function in a loop until the instance STOP condition is True
		@param sets: List of sets (i.e., (sub)workflows) to run (i.e., receive and process requests)
		@type sets: List[str]
		@param request_in: List of users' requests within specified @sets to be processed (i.e., path to request folder)
		@type request_in: List[str] 
		@param conf: VIFI Node configuration
		@type conf_in: dict
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		'''
		
		try:
			# Make sure that VIFI server configuration exist 
			if not conf:
				if self.vifi_conf:
					conf=self.vifi_conf
				else:
					print('Error: No VIFI server configuration exists')
					sys.exit()
					
			while not self.stop:
				self.vifiRun(sets, request_in, conf)
				time.sleep(conf['domains']['proc_int'])
		except:
			result='Error: "vifiRunLoop" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
		finally:
			if flog:
				flog.close()
			
		
	if __name__ == '__main__':
		
		import logging
		from vifi import vifi
		
		logger = multiprocessing.log_to_stderr()
		#logger.setLevel(logging.INFO)
		#logger.warning('doomed')
		logger.setLevel(logging.DEBUG)
		
		# Parse input arguments
		parser = argparse.ArgumentParser()
		parser.add_argument('--sets', nargs='*', help='List of sets to be processed', default=None)	# List of sets to be processed
		parser.add_argument('--vifi_conf',help='VIFI configuration file for current instance of VIFI server', default='vifi_config.yaml')	# List of sets to be processed
		arguments = parser.parse_args()
		
		# Create a VIFI server instance (Created by BaseManager to be shared between processes)
		BaseManager.register('vifi',vifi)
		m=BaseManager()
		m.start()
		s=m.vifi(arguments.vifi_conf)
		
		# Create list of processes to run different VIFI functionalities
		p=[]
		p.append(Process(target=s.unpackCompressedRequestsLoop,kwargs={'sets':arguments.sets}))
		p.append(Process(target=s.vifiRunLoop,kwargs={'sets':arguments.sets}))
		
		# Run the created VIFI processes
		for i in p:
			i.start()

		# Keep running VIFI server till receiving a STOP request 
		while True:
			lines=select.select([sys.stdin], [], [], 1)[0]
			if 'stop' in [x.readline().strip().lower() for x in lines]:
				p1=Process(target=s.end)
				p1.start()
				p1.join()
				break
		for i in p:
			i.join()
		p.clear()
				