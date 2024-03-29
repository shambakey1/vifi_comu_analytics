'''
Created on Mar 29, 2018

@author: Mohammed Elshambakey
@contact: shambakey1@gmail.com
'''

import yaml, time, os, sys, shutil, json, uuid, requests, traceback, select, multiprocessing, paramiko, glob
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

	def __init__(self, vifi_conf_f:str=None):
		'''
		VIFI Constructor
		@param vifi_conf_f: Path to VIFI configuration file
		@type vifi_conf: str
		'''
		
		# Initialize VIFI instance parameters
		self.vifi_conf_f = ''  # Path to VIFI configuration file for current VIFI instance
		self.vifi_conf = {}  # VIFI configuration dictionary for current VIFI instance
		self.req_list = {}  # Dictionary of created requests by current VIFI Node
		self.nifi_tr_res_flows = []  # List of deployed NIFI templates to transfer results between NIFI remote sites
		self.stop = False  # If TRUE, the current VIFI instance stops
			
		# Load VIFI configuration file
		try:
			if vifi_conf_f and os.path.isfile(vifi_conf_f):
				self.loadVIFIConf(vifi_conf_f)
			else:
				print("Error: No VIFI configuration file has been passed to this instance")
				sys.exit()
		except:
			result = 'Error: "VIFI constructor" function has error(vifi_server): '
			print(result)
			traceback.print_exc()
	
	def end(self):
		''' Stop current VIFI instance
		'''
		
		self.stop = True
	
	def dump_conf(self, conf:dict, outfile:str, flog:TextIOWrapper=None) -> None:
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
				with open(outfile, 'w') as f:
					yaml.dump(conf, f, default_flow_style=False)
					
		except:
			result = 'Error: "dump_conf" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
		
	def load_conf(self, infile:str, flog:TextIOWrapper=None) -> dict:
		''' Loads user configuration file.
		@param infile: Path and name of the user input YAML configuration file
		@type infile: str  
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		@return: User configuration file as YAML object
		@rtype: dict
		'''
	
		try:
			if infile and os.path.isfile(infile):
				with open(infile, 'r') as f:
					return yaml.load(f)
			else:
				print('Error: No user configuration file is specified')
		except:
			result = 'Error: "load_conf" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def checkInputFiles(self, in_file_root_loc:str, conf_in_total:dict, flog:TextIOWrapper=None) -> bool:
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
			for key, val in conf_in_total.items():
				if val == 'f' and not os.path.isfile(os.path.join(in_file_root_loc, key)):  # Check file
					print('Error: Could not find user required input file ' + os.path.join(in_file_root_loc, key))
					return False
				elif val == 'd' and not os.path.isdir(os.path.join(in_file_root_loc, key)):
					print('Error: Could not find user required input directory ' + os.path.join(in_file_root_loc, key))
					return False
				elif not os.path.exists(os.path.join(in_file_root_loc, key)):
					print('Error: Could not find user required input file/directory ' + os.path.join(in_file_root_loc, key))
					return False
				
			return True
		except:
			result = 'Error: "CheckInputFiles" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def getPromMetricsNames(self, prom_path:str, uname:str, upass:str, fname:str, fname_path:str, flog:TextIOWrapper=None) -> List[str]:
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
			metrics_req = requests.get(prom_path + "label/__name__/values", auth=(uname, upass))
			metrics_names = []  # List containing 
			if metrics_req.ok:  # Check Prometheus can be contacted
				metrics_names = metrics_req.json()['data']
				if not metrics_names:  # Check metrics names is not empty
					print('Prometheus has no metrics')
					sys.exit()
			else:
				print("Could not get metrics names from Prometheus")
				sys.exit()
				
			if fname:  # Dump metrics names as a JSON file if a JSON file path is provided
				with open(os.path.join(fname_path, fname), 'w') as f:
					json.dump(metrics_names, f)
			return metrics_names  # Return metrics names
		except:
			result = 'Error: "getPromMetricsNames" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def getMetricsNames(self, metrics_f:str, flog:TextIOWrapper=None) -> List[str]:
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
			result = 'Error: "getMetricsNames" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def getMetricsValues(self, m:List[str], start_t:float, end_t:float, prom_path:str, step:int, uname:str, upass:str, \
						write_to_file:bool, fname:str, fname_path:str, flog:TextIOWrapper=None) -> dict:
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
		# TODO: If start_t is not specified, then start query from the earliest possible timedate. But this depeneds on how long Prometheus stores data series, and the incremental step
		
		try:
			res = None
			res_values = {}  # Initial metric values is empty
		
			if start_t and not end_t:
				end_t = start_t
			elif end_t and not start_t:
				start_t = end_t
			elif not start_t and not end_t: 
				start_t = end_t = time.time()
			elif start_t > end_t:  # Query metric values within time interval
				print("Error: start time cannot be greater than end time to collect metric data")
				sys.exit()
				
			for mi in m:
				res = requests.get(prom_path + "query_range", auth=(uname, upass), params={'query':mi, 'start':start_t, 'end':end_t, 'step':step})
				if res.ok:  # Check Prometheus can be contacted for current metric
					res_values[mi] = res.json()['data']['result']
				else:
					res_values[mi] = "Error: cannot contact Prometheus for metric " + mi
					
			if write_to_file:
				if fname:  # Dump metric values as a JSON file if one is provided
					with open(os.path.join(fname_path, fname), 'w') as f:
						json.dump(res_values, f)
				else:  # Dump each metric values in a separate JSON file if no JSON file is provided
					for mi in m:
						with open(os.path.join(fname_path, mi + '_' + str(start_t) + '_' + str(end_t) + '.json'), 'w') as f:
							json.dump(res_values[mi], f)
					
			return res_values  # Return metrics names
		except:
			result = 'Error: "getMetricsValues" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def descVIFI(self, flog:TextIOWrapper=None):
		''' Prints general description about current VIFI instance '''
		
		try:
			if self.vifi_conf:
				print(str(self.vifi_conf))
			else:
				print('Current VIFI instance has no configuration')
		except:
			result = 'Error: "descVIFI" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()	
	
	def loadVIFIConf(self, conf_f:str=None, flog:TextIOWrapper=None) -> None:
		''' Load VIFI configuration for VIFI Node and make any necessary initialization for (sub)workflows
		@param conf_f: VIFI configuration file name (in YAML)
		@type conf_f: str
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)  
		'''
		
		try:
			if conf_f and os.path.isfile(conf_f):  # Check the existence of the general VIFI configuration file
				self.vifi_conf_f = conf_f
				with open(conf_f, 'r') as f:
					self.vifi_conf = yaml.load(f)
			else:
				if not self.vifi_conf:
					print('Error: could not find VIFI general configuration')
					sys.exit()
				
			# Info for root request directory
			root_script_path = self.vifi_conf['domains']['root_script_path']['name']  # Root directory for different domains requests
			root_script_path_mode = self.vifi_conf['domains']['root_script_path']['mode']  # Mode of requests root directory
			root_script_path_exist = self.vifi_conf['domains']['root_script_path']['exist_ok']  # If true, use already existing folder if one exists
			# FIXME: the following instruction should be used with the proper 'mode' configuration
			# os.makedirs(root_script_path,mode=root_script_path_mode,exist_ok=root_script_path_exist)	# Create requests root directory if not exists
			os.makedirs(root_script_path, exist_ok=root_script_path_exist)  # Create requests root directory if not exists
			
			# Default info for request structure within each domain 
			request_path_in = self.vifi_conf['domains']['script_path_in']['name']  # Path to receive requests within each domain
			request_path_in_mode = self.vifi_conf['domains']['script_path_in']['mode']  # Mode for received requests folder
			request_path_in_exist = self.vifi_conf['domains']['script_path_in']['exist_ok']  # If true, use already existing folder if one exists
			
			request_path_out = self.vifi_conf['domains']['script_path_out']['name']  # Path to output results within each domain
			request_path_out_mode = self.vifi_conf['domains']['script_path_out']['mode']  # Mode for output results folder
			request_path_out_exist = self.vifi_conf['domains']['script_path_out']['exist_ok']  # If true, use already existing folder if one exists
			
			request_path_failed = self.vifi_conf['domains']['script_path_failed']['name']  # Path to failed results within each domain
			request_path_failed_mode = self.vifi_conf['domains']['script_path_failed']['mode']  # Mode for failed results folder
			request_path_failed_exist = self.vifi_conf['domains']['script_path_failed']['exist_ok']  # If true, use already existing folder if one exists
			
			log_path = self.vifi_conf['domains']['log_path']['name']  # Path to logs within each domain
			log_path_mode = self.vifi_conf['domains']['log_path']['mode']  # Mode for logs folder
			log_path_exist = self.vifi_conf['domains']['log_path']['exist_ok']  # If true, use already existing folder if one exists
			
			# req_res_path_per_request=self.vifi_conf['domains']['req_res_path_per_request']['name']	# Path to intermediate results folder within each domain
			# req_res_path_per_request_mode=self.vifi_conf['domains']['req_res_path_per_request']['mode']	# Mode for logs folder
			# req_res_path_per_request_exist=self.vifi_conf['domains']['req_res_path_per_request']['exist_ok']	# If true, use already existing folder if one exists
			
			for d in self.vifi_conf['domains']['sets']:  # Create a sub-directory for each domain under the requests root directory
				# FIXME: the following commented instruction should be used whith the proper 'mode' configuration
				# os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name']),mode=conf['domains']['sets'][d]['mode'],exist_ok=conf['domains']['sets'][d]['exist_ok'])
				# os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],request_path_in),mode=request_path_in_mode,exist_ok=request_path_in_exist)
				# os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],request_path_out),mode=request_path_out_mode,exist_ok=request_path_out_exist)
				# os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],request_path_failed),mode=request_path_failed_mode,exist_ok=request_path_failed_exist)
				# os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],log_path),mode=log_path_mode,exist_ok=log_path_exist)
				# os.makedirs(os.path.join(root_script_path,conf['domains']['sets'][d]['name'],req_res_path_per_request),mode=req_res_path_per_request_mode,exist_ok=req_res_path_per_request_exist)
				os.makedirs(os.path.join(root_script_path, self.vifi_conf['domains']['sets'][d]['name']), exist_ok=self.vifi_conf['domains']['sets'][d]['exist_ok'])
				os.makedirs(os.path.join(root_script_path, self.vifi_conf['domains']['sets'][d]['name'], request_path_in), exist_ok=request_path_in_exist)
				os.makedirs(os.path.join(root_script_path, self.vifi_conf['domains']['sets'][d]['name'], request_path_out), exist_ok=request_path_out_exist)
				os.makedirs(os.path.join(root_script_path, self.vifi_conf['domains']['sets'][d]['name'], request_path_failed), exist_ok=request_path_failed_exist)
				os.makedirs(os.path.join(root_script_path, self.vifi_conf['domains']['sets'][d]['name'], log_path), exist_ok=log_path_exist)
				# os.makedirs(os.path.join(root_script_path,self.vifi_conf['domains']['sets'][d]['name'],req_res_path_per_request),exist_ok=req_res_path_per_request_exist)	

		except:
			result = 'Error: "loadVIFIConf" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()	
			
	def checkServiceComplete(self, client:docker.client.DockerClient, service_name:str, task_num_in:int, ttl:int=3600, \
							flog:TextIOWrapper=None) -> bool:
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
		
		# ## Checks if each task in task_num has completed
		try:
			while ttl:
				try:
					ser = client.services.get(service_name)
					task_num = task_num_in
					for t in ser.tasks():
						if t["Status"]["State"] == "complete":
							task_num -= 1
					if task_num == 0:
						return True
				except:
					ttl -= 1
				time.sleep(1)
			return False
		except:
			result = 'Error: "checkServiceComplete" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def checkServiceImage(self, docker_img_set:dict, user_img:str, flog:TextIOWrapper=None) -> str:
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
			if (user_img and 'any' in [x.lower() for x in docker_img_set.keys()]) or user_img in docker_img_set.keys():  # Use end-user specified container image if VIFI node allows any container image, or user selected one of the allowed images by VIFI node
				return user_img
			else:
				return None
		except:
			result = 'Error: "checkServiceImage" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def setServiceNumber(self, docker_rep:str, user_rep:int=None, flog:TextIOWrapper=None) -> int:
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
			def_rep = 1  # Default number of service tasks
			if str(docker_rep).lower() == 'any':  # VIFI Node allows any number of service tasks
				if user_rep:
					return user_rep
				else:
					return def_rep  # Default number of service tasks if user does not specify specific number of tasks
			else:
				if user_rep and user_rep < int(docker_rep):
					return user_rep  # Return required number of service tasks as it is allowed by VIFI Node
				else:
					return int(docker_rep)  # User required number of tasks exceeds allowed number by VIFI Node. Thus, reduce number of tasks to that allowed by VIFI Node
		except:
			result = 'Error: "setServiceNumber" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def setServiceThreshold(self, ser_check_thr:str, user_thr:int=None, flog:TextIOWrapper=None) -> int:
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
			def_ttl = 3600  # Default ttl
			if str(ser_check_thr).lower() == 'any':
				if user_thr:
					return user_thr
				else:
					return def_ttl
			else:
				if user_thr and user_thr < int(ser_check_thr):
					return user_thr  # User specified threshold does not exceed maximum allowed threshold by VIFI Node
				else:
					return int(ser_check_thr)  # Return maximum allowed threshold by VIFI Node as user requires more than what is allowed
		except:
			result = 'Error: "setServiceThreshold" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
			
	def createUserService(self, client:docker.client.DockerClient, service_name:str, docker_rep:int, script_path_in:str, request:str, container_dir:str, \
						data_dir:dict, user_data_dir:dict, work_dir:str, script:str, docker_img:str, docker_cmd:str, ttl,
						user_args:List[str]=[], user_envs:List[str]=None, user_mnts:List[str]=None, user=None, groups=None, flog:TextIOWrapper=None) -> docker.models.services.Service:
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
			envs = ['MY_TASK_ID={{.Task.Name}}', 'SCRIPTFILE=' + script, 'ttl=' + str(ttl)]  # Initialize list of environment variables
			if user_envs:  # Append user environment variables if any
				envs.extend(user_envs)
			
			# Mount the user request folder to the specified container_dir if any. Otherwise, the user request
			# folder is mapped to the root directory in the container.
			if not container_dir:
				container_dir = os.path.join(os.path.abspath(os.sep), request)
			mnts = [os.path.join(script_path_in, request) + ":" + container_dir + ":rw"]  # Initialize list of mounts for user'vifi_server request
				
			# Mount the data directories
			if user_data_dir:
				for x in user_data_dir.keys():  # mount data physical path at VIFI Node to user specified paths
					mnts.append(data_dir[x]['path'] + ":" + user_data_dir[x]['container_data_path'])
				
			# Append any additional user mounts (which should be in the form source:target:options) relative to the user request directory 
			if user_mnts:
				for x in user_mnts:
					if x[0] == '/':  # User mount should be relative to the user request directory. Thus, any 'source' should not start with '/'
						x = x[1:]
					x = os.path.join(script_path_in, request, x)
					mnts.append(x)
			
			# Determine the user and group(s) used to run the container services if none is provided
			if not user:
				user = str(os.getuid())
			if not groups:
				groups = [str(os.getgid())]
				
			# Now, create the required (docker) service, and return it
			return client.services.create(name=service_name, mode={'Replicated':{'Replicas':docker_rep}}, restart_policy=\
								{'condition':'on-failure'}, mounts=mnts, workdir=work_dir, env=envs, image=docker_img, \
								command=docker_cmd + ' ' + script, args=[str(i) for i in user_args], user=user, groups=groups)
		except:
			result = 'Error: "createUserService" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
		
	def checkSerDep_ORG(self, client:docker.client.DockerClient, ser_name:str, user_conf:dict, flog:TextIOWrapper=None) -> bool:
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
		
		# TODO: Currently, this method returns True if each previous service is completed. In the future, more sophisticated behavior may be needed
		
		try:
			# Get list of preceding services that should complete before current service
			dep_servs = user_conf['services'][ser_name]['dependencies']['ser']
			
			# Check satisfaction of each service if any (i.e., each service should reach the desired state)
			if dep_servs:
				for ser in dep_servs:
					# First, check service existence
					if ser not in [x.name for x in client.services.list()]:
						return False
					
					# Check if service is complete. Note that we do not have to wait for the previous service ttl to check
					# completeness because the previous service should have already completed. Thus, the ttl is passed as 0
					if not self.checkServiceComplete(client, ser, ser.attrs['Spec']['Mode']['Replicated']['Replicas'], 0):
						return False
			
			return True
		except:
			result = 'Error: "checkSerDep" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def checkSerDep(self, servs:dict, ser_name:str, user_conf:dict, flog:TextIOWrapper=None) -> bool:
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
		
		# TODO: Currently, this method returns True if each previous service is completed. In the future, more sophisticated behavior may be needed
		
		try:
			# Get list of preceding services that should complete before current service
			dep_servs = []
			for i in user_conf['services']:  # The loop is needed in case of investigating dependencies for iterative service. In current VIFI implementation, an iterative service is composed of the basic service name, plus a UUID
				if i in ser_name:
					dep_servs = user_conf['services'][i]['dependencies']['ser']
					break
			
			# Check satisfaction of each service if any (i.e., each service should reach the desired state)
			if dep_servs:
				for ser in dep_servs:
					# Check service existence
					if ser in servs and servs[ser]['cur_iter'] < servs[ser]['max_rep']:
						return False
					
			return True
		
		except:
			result = 'Error: "checkSerDep" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def checkFnDep(self, user_conf:dict, flog:TextIOWrapper=None) -> bool:
		''' Check if precedence constraints, defined in terms of functions, are satisfied
		@param user_conf: User configuration file
		@type user_conf: dict
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		@return: True if precedence functions are satisfied. Otherwise, False
		@rtype: bool 
		'''
		
		# TODO: Currently, this method alawys returns True. In the future, more sophosticated check should be done
		try:
			return True
		except:
			result = 'Error: "checkFnDep" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def checkDataOpt(self, conf:dict, user_conf:dict, flog:TextIOWrapper=None) -> bool:
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
		
		# FIXME: Currently, we assume all user required data options can be satisfied. Later, this method may need to communicate with security layer
		try:
			return True
		except:
			result = 'Error: "checkDataOpt" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def checkSerName(self, ser:str='', iter_no:int=0, client:docker.client.DockerClient=None, flog:TextIOWrapper=None) -> str:
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
			ser = self.getSerName(ser, iter_no, flog)
			for x in client.services.list():
				if ser in x.name:
					return None
			
			return ser

		except:
			result = 'Error: "checkSerName" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
		
	def createMetadata(self):
		''' Create metadata file that gives additional information about sent files between VIFI Nodes.
		The metadata file can be used in log tracing. The metadata file should be stored by the remote VIFI Node in the log folder of the corresponding request
		Currently, the created file name should end with ".log.yml" or ".log.yaml"
		'''
		
		# TODO: Implement
		pass
		
		
	def getSerName(self, ser_name:str='', iter_no:int=0, flog:TextIOWrapper=None) -> str:
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
		
		# TODO: There can be better ways to generate unique service name
		try:
			if iter_no:
				return ser_name + "_" + str(iter_no)
			else:
				return ser_name
		except:
			result = 'Error: "getSerName" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def delService(self, client:docker.client.DockerClient, ser_name:str, term_time:str, flog:TextIOWrapper=None) -> None:
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
		
		# TODO: Currently, this function either directly removes the service, or leaves it indefinitely. In the future, there should be a separate thread (such that other requests are not delayed until the specified service is removed) to monitor services and remove them according to specified termination time.
		try:
			if term_time != 'inf':
				client.services.get(ser_name).remove()
		except:
			result = 'Error: "delService" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def checkTransfer(self, transfer_conf:dict, servs:dict, ser:str, cond_path:str='', flog:TextIOWrapper=None) -> bool:
		''' Check if it is required to make a transfer for current service iteration.
		@attention: Current service iteration number is 1-based, meaning that after a service finishes, it should have incremented iteration number by 1. Thus, if the service iteration number, this means the service has accomplished 1 iteration. This information is important for comparsion between current service iteration number and the service maximum repetitions.
		@param transfer_conf: The transfer configuration. It is a common structure between different transfer sections (e.g., s3, nifi)
		@type transfer_conf: dict
		@param servs: Dictionary of services with different parameters including current service iteration and maximum repetitions for current service
		@type servs: dict 
		@param ser: Current service name
		@type ser: str  
		@param cond_path: Directory path that contains conditional files (i.e., files that, if exist, mean that it is ok to transfer results)
		@type cond_path: str 
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		@return: True if transfer is required. False otherwise
		@rtype: bool 
		'''
		
		try:
			
			# Lower case the condition string
			cond = transfer_conf['condition'].lower()
			
			# Split the condition string to a list of conditions
			cond = cond.strip().split()
			
			# Determine if it is required to transfer results (in current iteration)
			cond = ['True' if x == 'all' else x for x in cond]  # If True, then transfer any results for each iteration

			cond = ['False' if x == 'never' else x for x in cond]  # If True, then never transfer any results for any iteration

			if servs[ser]['cur_iter'] == servs[ser]['max_rep']:  # If True, then transfer results only if it is already last iteration for current service
				cond = ['True' if x == 'last_iteration' else x for x in cond]
			else:
				cond = ['False' if x == 'last_iteration' else x for x in cond]
			
			if servs[ser]['cur_iter'] < servs[ser]['max_rep']:  # If True, then transfer results of current service iteration only if it not the last iteration
				cond = ['True' if x == 'all_but_last_iteration' else x for x in cond]
			else:
				cond = ['False' if x == 'all_but_last_iteration' else x for x in cond]
			
			if os.path.isfile(os.path.join(cond_path, 'stop.iterating')):  # If True, then transfer results of current service iteration only if the service stops iterations (i.e., stop.iterating file exists)
				cond = ['True' if x == 'stop_iteration' else x for x in cond]
			else:
				cond = ['False' if x == 'stop_iteration' else x for x in cond]
			
			# Re-group the transfer condition string
			cond = ' '.join(cond)
			# print('DEBUG: cond: '+str(cond)+': '+str(eval(cond)))
			# Evaluate the transfer condition string
			return eval(cond)
		
		except:
			
			result = 'Error: "checkTransfer" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()

	def actOnResults(self, conf:dict, res_cur_dir:str, res_dest_dir:str, flog:TextIOWrapper=None) -> None:
		''' Act upon intermediate results after current service (iteration) finishes, and before the next 
		service (iteration) starts. For each file, actions are executed in the given sequence. Current actions include:
		- copy: Copies specified file from current results directory (e.g., working directory) to destination results directory. The copied file is kept in current results directory because it may be needed by future services (e.g., stop.iterating file)
		- move: Moves specified file from current results directory (e.g., working directory) to destination results directory. The copied file should be moved because the next service (iteration) may depend on an updated version of this file. Otherwise, the next service (iteration) may start running using the outdated version. Move is the default action
		@param conf: Results configuration as specified in the user YAML configuration file
		@type conf: dict
		@param res_cur_dir: Current directory results (usually the working directory of the user's request)
		@type res_cur_dir: str
		@param res_dest_dir: Target directory for results (usually a sub-folder named 'results' under the working directory of the user's request folder)
		@type res_dest_dir: str
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		@return: True if transfer is required. False otherwise
		'''
		
		try:
			
			#for f_res in conf:
			for i in conf:
				for f_res in glob.glob(os.path.join(res_cur_dir,i)):	# If the result name is specified with pattern, instead of literal name, then the result name should be extended first to all matching files and directories
					#for f_res in j:
					# Check if the result is file or directory
					if os.path.isfile(f_res):  # Result is file
						# Perform required sequence of actions on result files
						for act in conf[i]:
							if act['action'].lower() == 'copy':
								# print('DEBUG: actOnResult: copy file '+str(os.path.join(res_cur_dir,f_res))+' to '+str(os.path.join(res_cur_dir,res_dest_dir,f_res))+'\n')
								shutil.copy(f_res, os.path.join(res_cur_dir, res_dest_dir, i))
							else:
								# print('DEBUG: actOnResult: move file '+str(os.path.join(res_cur_dir,f_res))+' to '+str(os.path.join(res_cur_dir,res_dest_dir,f_res))+'\n')
								shutil.move(f_res, os.path.join(res_cur_dir, res_dest_dir, i))
					elif os.path.isdir(f_res):  # Result is a directory
						# Remove the directory from the destination path if already exist there
						if os.path.isdir(os.path.join(res_cur_dir, res_dest_dir, i)):
							shutil.rmtree(os.path.join(res_cur_dir, res_dest_dir, i))
						# Perform required set of actions on result directories
						for act in conf[i]:
							if act['action'].lower() == 'copy':	
								shutil.copytree(f_res, os.path.join(res_cur_dir, res_dest_dir, i))
							else:
								shutil.move(f_res, os.path.join(res_cur_dir, res_dest_dir, i))	
					else:
						if flog:
							flog.write("Cannot find result " + i + " at " + repr(time.time()) + "\n")
		
		except:
			
			result = 'Error: "actOnResults" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def toRemove(self, conf:dict, data_path:str, flog:TextIOWrapper=None) -> None:
		''' Remove specified set of files/directories under the specified path after current service (iteration) 
		finishes, and before the next service (iteration) begins. The specified files/folder represent dependencies 
		for the current service (iteration), and they should be updated before the next service (iteration) starts. 
		Otherwise, the next service (iteration) will run with outdated data.
		@param conf: User configuration containing set of files/folder to be removed 
		@type conf: dict
		@param data_path: Root path of files/folder to be removed
		@type data_path: str 
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)  
		'''
		
		try:
			for i in conf:
				for j in glob.glob(os.path.join(data_path,i)):	# If the result name is specified with pattern, instead of literal name, then the result name should be extended first to all matching files and directories
					for f in j:
						# print("DEBUG: remove result "+str(f)+" from path "+str(data_path)+"\n")
						if os.path.isfile(f):  # To remove a file
							os.remove(f)
						elif os.path.isdir(f):  # To remove a folder
							shutil.rmtree(f)
		except:
			result = 'Error: "toRemove" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
		
	def nifiTransfer(self, user_nifi_conf:dict, data_path:str, res_id:str='', pg_name:str=None, tr_res_temp_name:str='tr_res_temp', \
					flog:TextIOWrapper=None) -> str:
		''' Transfer required results as a compressed zip file using NIFI
		@attention: Current implementation just creates the compressed file to be transfered by NIFI. Current implementation does not transfer the file by itself. The transfer process is done by NIFI workflow design
		@note: If result files and/or directories are specified, then only the results files/directories are transferred. Otherwise, the whole results directory is transfered
		@param user_nifi_conf: User configurations related to NIFI
		@type user_nifi_conf: dict  
		@param data_path: Directory path of file to be transfered
		@type data_path: str 
		@param res_id: Results UUID which can be useful for log tracing (e.g., to trace a specific result sent from specific VIFI Node A to specific VIFI Node B)
		@type res_id: str  
		@param pg_name: NIFI Processor group name corresponding to required set
		@type pg_name: str 
		@param tr_res_temp_name: NIFI Transfer results template name. Defaults to 'tr_res_temp' template
		@type tr_res_temp_name: str 
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		@return: Name of the (uniquely identified) compressed result file, if successful, without path. Otherwise, and empty string
		@rtype: str
		'''
		
		try:
			
			# Copy results file(s) and/or directories, if specified, to the created user_name directory. Otherwise, copy the whole results directory to a user_name directory, under the results directory, if not already exists
			if 'results' in user_nifi_conf and user_nifi_conf['results']:
				# Create the user_name directory to hold the intermediate results that will be transfered
				os.makedirs(os.path.join(data_path, user_nifi_conf['archname']), exist_ok=False)
				for j in [glob.glob(os.path.join(data_path,i)) for i in user_nifi_conf['results']]:	# If the result name is specified with pattern, instead of literal name, then the result name should be extended first to all matching files and directories
					for res in j:
						if os.path.isfile(res):
							shutil.copy(res, os.path.join(data_path, user_nifi_conf['archname']))
						elif os.path.isdir(res):
							shutil.copytree(res, os.path.join(data_path, user_nifi_conf['archname'], os.path.basename(res)))
			else:
				shutil.copytree(data_path, os.path.join(data_path, user_nifi_conf['archname']))
			
			# Compress the created user_name directory
			shutil.make_archive(os.path.join(data_path, user_nifi_conf['archname']), 'zip', data_path, user_nifi_conf['archname'])
			
			# Remove the created user_name directory
			shutil.rmtree(os.path.join(data_path, user_nifi_conf['archname']), ignore_errors=True)
			
			# Identify the compressed results if required
			res_name = os.path.join(data_path, user_nifi_conf['archname'] + '.zip')
			if res_id:
				shutil.move(res_name, os.path.join(data_path, user_nifi_conf['archname'] + '.' + res_id + '.zip'))
				res_name = os.path.join(data_path, user_nifi_conf['archname'] + '.' + res_id + '.zip')
						
			# Retrieve processor group for the specified set
			set_pg = canvas.get_process_group(pg_name)
			
			# Retrieve transfer results template
			tr_res_temp = templates.get_template_by_name(tr_res_temp_name)
			
			# Deploy the transfer results template and keep a reference for it
			tr_res_flow = templates.deploy_template(set_pg.id, tr_res_temp.id)
			self.nifi_tr_res_flows.append(tr_res_flow)
			
			# A reference to 'get result file' processor
			tr_res_get_results = tr_res_flow.flow.processors[0]
			
			# A reference to the 'remote site' to transfer results
			tr_res_remote = tr_res_flow.flow.remote_process_groups[0]
			
			# A reference to the connection between 'get results file' processor and the remote process group
			tr_res_conn = tr_res_flow.flow.connections[0]
			
			# Create an instance of RemoteProcessGroupsApi to update the remote process group
			rpg_api = RemoteProcessGroupsApi()
			
			# Specify the target URI for the remote site and update the remote site
			tr_res_remote.component.target_uri = user_nifi_conf['target_uri']
			tr_res_remote.component.target_uris = user_nifi_conf['target_uri']
			rpg_api.update_remote_process_group(tr_res_remote.id, tr_res_remote)
			
			# Update the reference to the modified remote process group
			req_remote_port = None
			while tr_res_remote.status.target_uri != user_nifi_conf['target_uri'] or \
			user_nifi_conf['target_remote_input_port'] not in [k.name for k in tr_res_remote.component.contents.input_ports]:
				tr_res_remote = canvas.get_remote_process_group(tr_res_remote.id)
			
			# Create an instance of the ConnectionsApi
			conn_api = ConnectionsApi()
			
			# Retrieve information about the required input port of the remote process group. This step should be done after updating the target_uri(vifi_server) of the remote process group
			while not req_remote_port:
				for k in tr_res_remote.component.contents.input_ports:
					if k.name == user_nifi_conf['target_remote_input_port']:
						req_remote_port = k
						break
			
			# Modify the connection to the remote process group to reflect the correct input port
			# tr_res_conn=conn_api.get_connection(tr_res_conn.id)
			tr_res_conn.destination_id = req_remote_port.id
			tr_res_conn.component.destination.id = req_remote_port.id
			
			# Update the connection to the required input port of the remote process group
			conn_api.update_connection(tr_res_conn.id, tr_res_conn)
			
			# Update the reference to the connection to the remote process group
			while tr_res_conn.status.destination_name != req_remote_port.name or \
			tr_res_conn.status.destination_id != req_remote_port.id:
			# tr_res_conn.status.aggregate_snapshot.destination_name!=req_remote_port.name or \
			# tr_res_conn.status.aggregate_snapshot.destination_id!=req_remote_port.id:
				tr_res_conn = conn_api.get_connection(tr_res_conn.id)
			
			# Modify the 'get results' processor to indicate the path and the name of the compressed results file
			tr_res_get_results = canvas.get_processor(tr_res_get_results.id, 'id')
			tr_res_get_results.component.config.properties['Input Directory'] = data_path
			tr_res_get_results.component.config.properties['File Filter'] = os.path.basename(res_name)
			
			# Update the 'get results' processor with the new attributes
			canvas.update_processor(tr_res_get_results, tr_res_get_results.component.config)
			
			# Update the reference to the 'get results' processor
			while tr_res_get_results.component.config.properties['Input Directory'] != data_path or \
			tr_res_get_results.component.config.properties['File Filter'] != os.path.basename(res_name):
				tr_res_get_results = canvas.get_processor(tr_res_get_results.id, 'id')
						
			# Start the 'get results' processor to start transferring results file
			canvas.schedule_processor(tr_res_get_results, True)
			while canvas.get_processor(tr_res_get_results.id, 'id').revision.version == tr_res_get_results.revision.version:
				# TODO: I think there should be a more restrict condition than checking version to ensure the processor has run 
				pass
			
			# Enable transmission of the remote process group to finish transfer of the results file
			while tr_res_remote.status.target_uri != user_nifi_conf['target_uri'] or \
			user_nifi_conf['target_remote_input_port'] not in [k.name for k in tr_res_remote.component.contents.input_ports]:
				tr_res_remote = canvas.get_remote_process_group(tr_res_remote.id)  # This step is to ensure the remote port still exists because the remote site may experience some problems
			tr_res_remote_stat = {'revision':tr_res_remote.revision, 'state':'TRANSMITTING', 'disconnectedNodeAcknowledged':True}
			rpg_api.update_remote_process_group_run_status(tr_res_remote.id, tr_res_remote_stat)
			while tr_res_remote.status.transmission_status != 'Transmitting':
				tr_res_remote = canvas.get_remote_process_group(tr_res_remote.id)
			
			# Check that the results file has been transmitted
			while tr_res_remote.status.aggregate_snapshot.flow_files_sent == 0:
				tr_res_remote = canvas.get_remote_process_group(tr_res_remote.id)
			
			### TIME TO REMOVE THE DEPLOYED TRANSFER REUSULTS TEMPLATE ###
			
			# Disable transmission of the remote process group and update reference to the remote process group
			tr_res_remote_stat = {'revision':tr_res_remote.revision, 'state':'STOPPED', 'disconnectedNodeAcknowledged':True}
			rpg_api.update_remote_process_group_run_status(tr_res_remote.id, tr_res_remote_stat)
			while tr_res_remote.status.transmission_status != 'NotTransmitting':
				tr_res_remote = canvas.get_remote_process_group(tr_res_remote.id)
			
			# Stop the 'get results' processor and update the reference to the 'get results' processor
			canvas.schedule_processor(tr_res_get_results, False)
			
			# Delete the 'get results' processor and the associated connection to the remote process group
			canvas.delete_processor(tr_res_get_results, force=True)
			
			# Delete the remote process group
			rpg_api.remove_remote_process_group(tr_res_remote.id, version=tr_res_remote.revision.version)
			
			# PRECAUTION: Delete the compressed result file if still exists. Otherwise, the compressed file may conflict with the compressed result files of other services
			if os.path.isfile(os.path.join(data_path, res_name)):
				os.remove(os.path.join(data_path, res_name))
			
			# Return (uniquely identified) compressed result file name, without path, to indicate transfer success
			return os.path.basename(res_name)
			
		except:
			result = 'Error: "nifiTransfer" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
				
			# Return False to indicate transfer failure
			return False
		
	def s3Transfer(self, user_s3_conf:dict, data_path:str, flog:TextIOWrapper=None) -> None:
		''' Transfer files to S3 bucket
		@param user_s3_conf: User configurations related to S3 bucket
		@type user_s3_conf: dict  
		@param data_path: Path of files to be transfered
		@type data_path: str  
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object) 
		''' 		
		
		import boto3, glob
		
		try:
			s3 = boto3.resource('s3')
			# If results are specified in the s3 section, then upload specified results to the s3 bucket
			if 'results' in user_s3_conf and user_s3_conf['results']:
				for j in [glob.glob(os.path.join(data_path,i)) for i in user_s3_conf['results']]:	# If the result name is specified with pattern, instead of literal name, then the result name should be extended first to all matching files and directories
					for res in j:
						if os.path.isfile(res):
							data = open(res, 'rb')
							key_obj = user_s3_conf['path'] + "/" + os.path.basename(res)
							s3.Bucket(user_s3_conf['bucket']).put_object(Key=key_obj, Body=data)  # In this script, we do not need AWS credentials, as this EC2 instance has the proper S3 rule
						elif os.path.isdir(res):
							for path, _, f_res in os.walk(res):
								for f in f_res:
									data = open(os.path.join(path, f), 'rb')
									key_obj = user_s3_conf['path'] + "/" + f
									s3.Bucket(user_s3_conf['bucket']).put_object(Key=key_obj, Body=data)  # In this script, we do not need AWS credentials, as this EC2 instance has the proper S3 rule

				
			# If no results are specified for the s3 section, then upload the whole results section
			else:
				for path, dir, f_res in os.walk(data_path):
					for f in f_res:
						data = open(os.path.join(path, f), 'rb')
						key_obj = user_s3_conf['path'] + "/" + f
						s3.Bucket(user_s3_conf['bucket']).put_object(Key=key_obj, Body=data)  # In this script, we do not need AWS credentials, as this EC2 instance has the proper S3 rule
		except:
			result = 'Error: "s3Transfer" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def sftpTransfer(self, user_sftp_conf:dict, data_path:str, \
					flog:TextIOWrapper=None) -> bool:
		''' Transfer input file to specified SFTP server
		@param user_sftp_conf: User configurations related to SFTP Server
		@type user_sftp_conf: dict  
		@param data_path: Path of files to be transfered
		@type data_path: str
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		@return: True if transfer succeeds. False otherwise
		@rtype: bool
		'''			
		
		try:

			# Extract required SFTP parameters from user configuration file
			host = user_sftp_conf['host']
			port = user_sftp_conf['port']
			username = user_sftp_conf['username']
			password = user_sftp_conf['password']
			dest_path = user_sftp_conf['dest_path']
			
			# needed to add host to trusted hosts file
			ssh_client = paramiko.SSHClient()
			ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			
			transport = paramiko.Transport((host, port))
			transport.connect(username=username, password=password)
			
			sftp_client = paramiko.SFTPClient.from_transport(transport)
			res = []  # True if files are sent correctly to the SFTP server. False, otherwise.
			
			# If results are specified in the sftp section, then upload specified results to the sftp
			if 'results' in user_sftp_conf and user_sftp_conf['results']:
				for j in [glob.glob(os.path.join(data_path,i)) for i in user_sftp_conf['results']]:	# If the result name is specified with pattern, instead of literal name, then the result name should be extended first to all matching files and directories
					for res in j:
						if os.path.isfile(res):
							sftp_client.put(res, os.path.join(dest_path, os.path.basename(res)))
						elif os.path.isdir(res):
							for path, _, f_res in os.walk(res):
								for f in f_res:
									sftp_client.put(os.path.join(path, f), os.path.join(dest_path, f))

			# If no results are specified for the sftp section, then upload the whole results section
			else:
				for path, _, f_res in os.walk(data_path):
					for f in f_res:
						sftp_client.put(os.path.join(path, f), os.path.join(dest_path, f))
			
			sftp_client.close()
			transport.close()
			return True
		
		except:
			result = 'Error: "sftpTransfer" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
			return False
		
	def changePermissionsRecursive(self, path:str, mode=0o777, flog:TextIOWrapper=None) -> None:
		''' Changes permissions of files and folders recursively under specified path
		@see https://www.tutorialspoint.com/How-to-change-the-permission-of-a-directory-using-Python
		@param path: Top path to change permissions
		@type path: str
		@param mode: Permissions mode to set_i
		@type mode: Oct    
		'''
		
		try:
			for root, dirs, files in os.walk(path, topdown=False):
				for dir_in in [os.path.join(root, d) for d in dirs]:
					if os.stat(dir_in).st_uid == os.getuid() and os.stat(dir_in).st_gid == os.getgid():
						os.chmod(dir_in, mode)
					
				for file in [os.path.join(root, f) for f in files]:
					if os.stat(file).st_uid == os.getuid() and os.stat(file).st_gid == os.getgid():
						os.chmod(file, mode)
			
				if os.stat(root).st_uid == os.getuid() and os.stat(root).st_gid == os.getgid():
					os.chmod(root, mode)	
					
		except:
			result = 'changePermissionsRecursive" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def checkCompressed(self, req:str) -> bool:
		''' Check if the input request is a compressed file
		@param req: Input request to be examined as a compressed file or not
		@type req: Str
		@return: True if the input request is a compressed file. Otherwise, returns False
		@rtype: Bool  
		'''
		
		# Currently, this function checks if the input file has the ".zip" extension
		if '.zip' in req:
			return True
		
		return False
	
	def getReqPartfromReqPath(self, req:str, sep:str='.') -> List[str]:
		''' Return request partitions from request path (i.e., request name, specific ID for this request, request extension)
		@param req: Request path
		@type req: Str
		@param sep: Separator in request name. Default is '.'
		@type sep: Str
		@return: List of request partitions (i.e., request name, specific ID for this request, request extension)
		@rtype: List[str]
		'''
		
		# Current implementation assumes the input request consists of the desired request name + '.' + UUID + '.' + extension
		return os.path.basename(req).split(sep=sep)
		
	def getReqNameFromPath(self, req:str, sep:str='.') -> str:
		''' Returns request name from received compressed file path
		@param req: Input request path
		@type req: Str
		@param sep: Separator in request name. Default is '.'
		@type sep: Str
		@return: Request name without any additions (e.g., request UUID, extension, ... etc)
		@rtype: Str  
		'''
		
		# Current implementation assumes the input request consists of the desired request name + '.' + if exists( UUID + '.' +) extension
		return os.path.splitext(os.path.basename(req))[0].split(sep=sep)[0]
	
	def getReqUUIDFromPath(self, req:str, sep:str='.') -> str:
		''' Return request UUID from received compressed file path
		@param req: Input request path
		@type req: Str
		@param sep: Separator in request name. Default is '.'
		@type sep: Str
		@return: Request UUID without any additions (e.g., request name, extension, ... etc)
		@rtype: Str  
		'''
		
		# Current implementation assumes the input request consists of the desired request name + '.' + if exists(UUID + '.' +) extension
		if len(self.getReqPartfromReqPath(req, sep)) == 3:
			return os.path.splitext(os.path.basename(req))[0].split(sep=sep)[1]
		
		return ''
	
	def getReqNameUUIDFromPath(self, req:str, sep:str='.') -> str:
		''' Return request UUID from received compressed file path
		@param req: Input request path
		@type req: Str
		@param sep: Separator in request name. Default is '.'
		@type sep: Str
		@return: Request request name + UUID without any additions (e.g., extension, ... etc)
		@rtype: Str  
		'''
		
		# Current implementation assumes the input request consists of the desired request name + '.' + UUID + '.' + extension
		return os.path.splitext(os.path.basename(req))[0]
		
	def unpackCompressedRequests(self, conf:dict=None, sets:List[str]=None, sep:str='.', flog:TextIOWrapper=None) -> None:
		''' Unpack any compressed requests under specified set_i(vifi_server) (i.e., (sub)workflow(vifi_server))
		@param conf: VIFI configuration file
		@type conf: dict
		@param sets: List of required sets (i.e., (sub)workflow(vifi_server)) to unpack incoming requests. Defaults to all sets if None is specified
		@type sets: List[str] 
		@param sep:  Separator in request name. Default is '.'
		@type sep: Str 
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
					conf = self.vifi_conf
					
			# If input sets are not specified, then load all sets in VIFI configuration if any
			if not sets:
				sets = conf['domains']['sets']
				
			# Traverse through all sets
			for dset in sets:
				# Determine path to compressed requests under specified set_i
				comp_path = os.path.join(conf['domains']['root_script_path']['name'], conf['domains']['sets'][dset]['name'], \
									conf['domains']['script_path_in']['name'])
				
				# List all requests under current set_i
				reqs = os.listdir(comp_path)
				
				# Unpack compressed files only, then remove the compressed file after extraction
				for req in reqs:
					# Unpack file according to file extension
					if self.checkCompressed(req):
						
						# Get the base request name without additions
						req_name = self.getReqNameFromPath(req)
						
						# Get the path to finished requests
						script_path_out = os.path.join(conf['domains']['root_script_path']['name'], conf['domains']['sets'][dset]['name'], \
										conf['domains']['script_path_out']['name'])
						
						# If a directory exists in the 'finished' with the same name, then move it to working directory. Then extract the compressed file to update the contents of the retrieved directory
						if os.path.exists(os.path.join(script_path_out, req_name)):
							shutil.move(os.path.join(script_path_out, req_name), os.path.join(comp_path, req_name))
							# Increment the maximum iteration number for all services in the returned request, as the returned request is going to run once more
							self.incMaxIterAllServicesinRequest(os.path.join(comp_path, req_name))
						
						# Now, extract the compressed request
						with ZipFile(os.path.join(comp_path, req)) as f:
							f.extractall(comp_path)
					
						# Remove compressed file after extraction
						os.remove(os.path.join(comp_path, req))
						
						# Change permissions for uncompressed folder (Currently, permissions are changed to 777 to allow writing by docker services into created folders)
						self.changePermissionsRecursive(os.path.join(comp_path, req).split('.zip')[0])
						
						# Check if the uncompressed folder has any log files
						if os.path.exists(os.path.join(comp_path, self.getReqNameUUIDFromPath(req, sep), ".log.yml")):
							rec_logf = os.path.join(comp_path, self.getReqNameUUIDFromPath(req, sep), ".log.yml")
						elif os.path.exists(os.path.join(comp_path, self.getReqNameUUIDFromPath(req, sep), ".log.yaml")):
							rec_logf = os.path.join(comp_path, self.getReqNameUUIDFromPath(req, sep), ".log.yaml")
						else:
							rec_logf = None
							
						# If the uncompressed folder has any log file, then move the log files to the request log
						if rec_logf:
							# Create log directory if not exists
							os.makedirs(os.path.join(self.vifi_conf['req_log_path'], req_name), exist_ok=True)
							# Move the found log file to the requst log directory under current VIFI node
							shutil.move(rec_logf, os.path.join(self.vifi_conf['req_log_path'], req_name))
		except:
			result = 'Error: "unpackCompressedRequests" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def unpackCompressedRequestsLoop(self, conf:dict=None, sets:List[str]=None, flog:TextIOWrapper=None) -> None:
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
					conf = self.vifi_conf
						
			while not self.stop:
				self.unpackCompressedRequests(conf, sets, flog)
				time.sleep(conf['domains']['unpack_int'])
		
		except:
			result = 'Error: "unpackCompressedRequestsLoop" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def logToMiddleware(self, middleware_conf:dict, body:dict={}, flog:TextIOWrapper=None) -> bool:
		''' Write log to Middleware
		@param middleware: The middleware configuration including the URL of the central log
		@type middleware: dict
		@param body: (Optional) contents of the log message
		@type body: dict
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		@return: True if log sent correctly. False, otherwise
		@rtype: bool  
		'''
		
		try:
			# Extract required middleware log parameters
			log_condition = middleware_conf['condition']
			log_url = middleware_conf['url']
			log_header = middleware_conf['header']
			
			# Send log message to middleware log
			if log_condition and body:
				r = requests.post(url=log_url, headers=log_header, json=body)
			
			# Check response. Return True if correct. False, otherwise
			if r.status_code == requests.codes.ok:
				return True
			else:
				return False
		
		except:
			result = 'Error: "logToMiddleware" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
					
	def reqLog(self, req_log_path:str, req_log:dict, req:str) -> None:
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
		os.makedirs(req_log_path, exist_ok=True)
		
		# Write request log to created log file. Log file is created if not already exists
		if not (req.endswith('.log.yml') or req.endswith('.log.yaml')):
			req = req + ".log.yml"
		with open(os.path.join(req_log_path, req), 'w') as f:
			yaml.dump(req_log, f)
			
	def reqsAnalysis(self, req_paths:List[str], req_analysis_f:str, req_analysis_path:str=None, prom_conf:dict=None, \
					metrics_values_path:str=None, metrics_values_f:str=None, flog:TextIOWrapper=None) -> pd.DataFrame:
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
			dt = []  # List to hold all analysis record of all requests
			cnt = 0  # Counter to index analysis records
			
			# Record Prometheus metrics if required
			if prom_conf:
				# Determine file path containing metrics names
				metrics_names = os.path.join(prom_conf['metrics_names_path'], \
									prom_conf['metrics_names_f'])
				
				# Retrieve required metrics names from file if exists. Otherwise, create file
				if os.path.isfile(metrics_names) and os.path.getsize(metrics_names) > 0:
					metrics = self.getMetricsNames(metrics_names, flog)
				else:
					os.makedirs(prom_conf['metrics_names_path'], exist_ok=True)
					metrics = self.getPromMetricsNames(prom_path=prom_conf['prometheus_url'], \
													uname=prom_conf['uname'], \
													upass=prom_conf['upass'], \
													fname=prom_conf['metrics_names_f'], \
													fname_path=prom_conf['metrics_names_path'], flog=flog)
				
				# Determine file name and path to record collected Prometheus metrics if required
				if not metrics_values_f:
					metrics_values_f = prom_conf['metrics_values_f']
				
				if not metrics_values_path:
					metrics_values_path = prom_conf['metrics_values_path']
			
			# Traverse through all required requests paths
			for reqf in req_paths:
				# Initialize prometheus variables
				with open(reqf, 'r') as x:
					req = yaml.load(x)
					for ser in req['services']:
						d = pd.DataFrame(data={'request':reqf, 'service':[ser], 'start':[float(req['services'][ser]['start'])], \
											'end':[float(req['services'][ser]['end'])], 'cmp_time':\
											[float(req['services'][ser]['end']) - float(req['services'][ser]['start'])], \
											'no_tasks':[int(req['services'][ser]['tasks'])]}, index=[cnt])
						dt.append(d)  # Append current record to collected analysis results
						cnt = cnt + 1  # Increment record index
				
					# Record Prometheus metrics if allowed by VIFI node
					if prom_conf:
						# Determine first time to record metrics as start time of first service in request
						metric_start = min([req['services'][ser]['start'] for ser in req['services']])
						
						# Determine last time to record metrics as the end time of last service in request 
						metric_end = max([req['services'][ser]['end'] for ser in req['services']])
						
						# If no file is given to record Prometheus metrics, then make file name that contains Prometheus metrics values. File name consists of request name, start time of first service, end time of last service 
						if not metrics_values_f:
							metrics_values_fname = ntpath.basename(reqf) + '_' + str(metric_start) + '_' + str(metric_end)
										
						# Record Prometheus metrics in created Prometheus file
						self.getMetricsValues(m=metrics, start_t=metric_start, end_t=metric_end, prom_path=prom_conf['prometheus_url'], \
								step=prom_conf['query_step'], uname=prom_conf['uname'], upass=prom_conf['upass'], \
								write_to_file=prom_conf['write_metrics'], fname=metrics_values_fname, \
								fname_path=metrics_values_path, flog=flog)
			
			# Join all analysis records together		
			df = pd.concat(dt)
			
			# Reorder collected records for a better view
			df = df[['request', 'service', 'no_tasks', 'start', 'end', 'cmp_time']]
			
			# Create final analysis file, or open an existing one if desired
			if req_analysis_f:
				if req_analysis_path and os.path.isdir(req_analysis_path):
					req_analysis_f = os.path.join(req_analysis_path, req_analysis_f)
				with open(req_analysis_f, 'w') as f:
					df.to_csv(f, index=False)
			
			# Return collected analysis records
			return df
		
		except:
			result = 'Error: "reqAnalysis" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
	
	def reqsDirAnalysis(self, req_log_dir:str, req_analysis_path:str=None, req_analysis_f:str=None, prom_conf:dict=None, \
					metrics_values_path:str=None, metrics_values_f:str=None, flog:TextIOWrapper=None) -> pd.DataFrame:
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
				req_logs = []
				
				# Collect all requests logs
				for path, dir, f_res in os.walk(req_log_dir):
					for f in f_res:
						req_logs.append(os.path.join(path, f))
						
				# Pass collected logs to @reqsAnalysis
				return self.reqsAnalysis(req_paths=req_logs, req_analysis_f=req_analysis_f, \
										req_analysis_path=req_analysis_path, prom_conf=prom_conf, \
					metrics_values_path=metrics_values_path, metrics_values_f=metrics_values_f, flog=flog)
			else:
				# Direcory path is not valid
				print('Error: directory path is not valid')
				return None
		
		except:
			result = 'Error: "reqDirAnalysis" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
				
			return None
		
	def serIterate(self, iter_conf:dict=None, ser_it_no:int=0, stop_itarting_path:str='stop.iterating', flog:TextIOWrapper=None) -> bool:
		''' Determine if it is required to repeat the service again. If no configuration is given, then the service is not repeated any more.
		Current implementation checks:
		1- If file named 'stop.iterating' exists, then iteration stops. The 'stop.iterating' file is produced by current service to stop iteration. The file can contain further information
		2- If condition 1 is not met, then maximum number of iterations has not been exceeded.
		3- If condition 1 is not met, if iterations are infinite by using the special word 'inf'
		@param iter_conf: Service configuration for the iterations
		@type iter_conf: dict
		@param ser_it_no: Current service iteration number. Incremented each time the service runs
		@type: int
		@param stop_itarting_path: Path to the file that, if exists, indicates requirement to stop iterating. The default path and name for the file is "stop.iterating" under current directory. This file is generated by the user during execution of the container analytics if some condition is met (e.g., performance has reached a specified threshold)
		@type stop_iterating_path: str
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		@return: True if service needs to be repeated. Otherwise, False
		@rtype: bool
		'''
		
		try:
			if os.path.isfile(stop_itarting_path):
				return False
			if iter_conf:
				if str.lower(str(iter_conf['max_rep']))=='inf' or ser_it_no < iter_conf['max_rep']:
					return True
			
			return False
		
		except:
			result = 'Error: "serIterate" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
				
			return None
	
	def getReqLastState(self, conf:dict=None, flog:TextIOWrapper=None) -> dict:
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
			servs = {}  # Initiate an empty dictionary for request's state
			
			# Iterate through services in request's configuration. Record only the unfinished services
			for ser in conf['services']:
				if conf['services'][ser]['iterative']['max_rep']=='inf' or conf['services'][ser]['iterative']['cur_iter'] < conf['services'][ser]['iterative']['max_rep']:
					servs[ser] = {}
					servs[ser]['max_rep'] = conf['services'][ser]['iterative']['max_rep']
					servs[ser]['cur_iter'] = conf['services'][ser]['iterative']['cur_iter']
			
			# Return request's state
			return servs
		
		except:
			result = 'Error: "getReqLastState" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
				
			return None
	
	def incMaxIterAllServicesinRequest(self, req_path:str=None, flog:TextIOWrapper=None) -> None:
		''' Increment maximum iterations number for all services in the configuration file of the input request folder
		@param req_path: Request folder containing configuration file
		@type req_path: str
		@param flog: Log file to record raised events
		@type flog: TextIOWrapper (file object)
		'''
		
		try:
			
			# Load the configuration file of request
			if req_path and os.path.isdir(req_path):
				with open(os.path.join(req_path, 'conf.yml'), 'r') as f:
					conf = yaml.load(f)
				
				# Increment the maximum iteration of all services in the specified request
				for ser in conf['services']:
					conf['services'][ser]['iterative']['max_rep'] += 1
				
				# Store back the modified configurations in the specified request
				with open(os.path.join(req_path, 'conf.yml'), 'w') as f: 	
					yaml.dump(conf, f, default_flow_style=False)
					
		except:
			result = 'Error: "incMaxIterAllServicesinRequest" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()			
			
	def vifiRun(self, sets:List[str]=None, request_in:List[str]=None, conf:dict=None) -> None:
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
			flog = ''
				
			# Make sure that VIFI server configuration exist 
			if not conf:
				if self.vifi_conf:
					conf = self.vifi_conf
				else:
					print('Error: No VIFI server configuration exists')
					sys.exit()

			# Acquire all existing sets if none specified
			if not sets:
				sets = conf['domains']['sets']
			# Traverse through required sets
			for dset in sets:	
			# Check if required set_i exists
				if dset in conf['domains']['sets']:
					### INITIALIZE USER PARAMETERS (APPLICABLE FOR ANY USER) ###
					conf_file_name = conf['user_conf']['conf_file_name']
		
					### INITIALIZE REQUIRED PATH VARIABLES FOR SPECIFIED SET ###
					script_path_in = os.path.join(conf['domains']['root_script_path']['name'], conf['domains']['sets'][dset]['name'], \
										conf['domains']['script_path_in']['name'])
					script_path_out = os.path.join(conf['domains']['root_script_path']['name'], conf['domains']['sets'][dset]['name'], \
										conf['domains']['script_path_out']['name'])
					script_path_failed = os.path.join(conf['domains']['root_script_path']['name'], conf['domains']['sets'][dset]['name'], \
										conf['domains']['script_path_failed']['name'])
					log_path = os.path.join(conf['domains']['root_script_path']['name'], conf['domains']['sets'][dset]['name'], \
										conf['domains']['log_path']['name'])
					req_res_path_per_request = os.path.join(conf['domains']['root_script_path']['name'], conf['domains']['sets'][dset]['name'], conf['domains']['req_res_path_per_request']['name'])
					data_dir = conf['domains']['sets'][dset]['data_dir']
					
					### LOGGING PARAMETERS ###
					flog_path = os.path.join(log_path, "out.log")
					flog = open(flog_path, 'a')
					flog.write("Scheduled by VIFI Orchestrator for set_i " + dset + " at " + str(time.time()) + "\n")
							
					### IF DOCKER IS USED FOR THIS SET, THEN INITIALIZE DEFAULT DOCKER PARAMETERS ###
					### SOME DOCKER PARAMETERS CAN BE OVERRIDEN BY END USER IF ALLOWED ###
					if 'docker' in conf['domains']['sets'][dset] and conf['domains']['sets'][dset]['docker']:
						docker_img_set = conf['domains']['sets'][dset]['docker']['docker_img']  # Set of allowed docker images
						docker_rep = conf['domains']['sets'][dset]['docker']['docker_rep']  # Maximum number of tasks that can be run by any user for this specific set_i
						ser_check_thr = conf['domains']['sets'][dset]['docker']['ttl']  # Default ttl for each (Docker) service
						docker_user = conf['domains']['sets'][dset]['docker']['user']  # User to run docker container
						docker_groups = conf['domains']['sets'][dset]['docker']['groups']  # List of groups to run docker container
						client = docker.from_env()
					else:
						print('Error: No containerization technique and/or stand alone service is specified to run (sub)workflow ' + dset)
						return
					
					### IF NIFI IS ENABLED FOR THIS SET, THEN INITIALIZE NIFI HOST AND REGISTRY IF EXISTS ###
					if conf['domains']['sets'][dset]['nifi']['transfer']:
						nipyapi.config.nifi_config.host = conf['domains']['sets'][dset]['nifi']['host']
						if conf['domains']['sets'][dset]['nifi']['registry']:
							nipyapi.config.registry_config.host = conf['domains']['sets'][dset]['nifi']['registry']
					
					# Acquire all requests under current set_i if none provided
					if not request_in:
						request_in = os.listdir(script_path_in)
						
					### USE PROVIDED SET FUNCTION IF EXISTS ###
					set_fun = conf['domains']['sets'][dset]['set_function']
					if set_fun:
						# TODO: Currently, only default set_i behavior is used
						pass
					else:
						### LOOP THROUGH REQUESTS AND PROCESS THEM (CURENTLY PROCESSING LOCATION IS NFS SHARED) ###
						for request in request_in:
							
							# Initialize final services status to check status of all underlying services for current request
							final_req_stat = True  # True is a temporary value. It changes to False if any underlying service fails, or due to any other failure to process the request
							
							# Update the internal list of processed requests with 'status=start'
							mes_time = time.time()
							self.req_list[request] = {}
							self.req_list[request]['start'] = mes_time
							self.req_list[request]['services'] = {}
							
							# Update central middleware log if required
							mes = {'request':request, 'start':mes_time}
							self.logToMiddleware(middleware_conf=conf['middleware']['log'], body=mes)
							
							# Initialize path parameters for current request
							script_processed = os.path.join(script_path_in, request)
							script_finished = os.path.join(script_path_out, request)
							script_failed = os.path.join(script_path_failed, request)
						
							# Check and load user configuration file if exists in current request. Otherwise, move to the next request
							if os.path.exists(os.path.join(script_path_in, request, conf_file_name)):
								conf_in = self.load_conf(os.path.join(script_path_in, request, conf_file_name))
							else:
								flog.write("Error: Configuration does not exist for " + request + " at " + str(time.time()) + "\n")
								# TODO: if this situation continues, then move to failed
								continue
							
							# Initiate a dictionary of services for current request. This set can be modified after reading the configuration file of current request (due to checkpointing, which is a future feature, some services may have already been finished)
							servs = self.getReqLastState(conf=conf_in)
							
							# Create a 'results' folder in current request (if not already exists) to keep output files.
							req_res_path_per_request = conf['domains']['req_res_path_per_request']['name']
							if not os.path.exists(os.path.join(os.path.join(script_path_in, request), req_res_path_per_request)):
								# req_res_path_per_request=req_res_path_per_request+"_"+str(uuid.uuid1())
								os.mkdir(os.path.join(os.path.join(script_path_in, request), req_res_path_per_request))  # To keep only required result files to be further processed or transfered.
							
							# Traverse all services of the current request
							for ser in conf_in['services']:
								# If current service already finished, then move to the next service
								if ser not in servs:
									continue
								
								# Record service name as current service being processed
								conf_in['curserv']=ser
								self.dump_conf(conf_in, os.path.join(script_path_in, request, conf_file_name), flog)
								
								# Set current service iteration
								ser_it = servs[ser]['cur_iter']
																
								# Initialize temporary service status to record status of created service (True if service succeeds)
								tmp_ser_stat = False
								
								# Check if the service still needs to iterate
								while self.serIterate(iter_conf=conf_in['services'][ser]['iterative'], ser_it_no=ser_it, stop_itarting_path=os.path.join(script_path_in, request, "stop.iterating")):
									# print('DEBUG: At new iteration, iteration: '+str(servs[ser]['cur_iter'])+', stop: '+str(os.path.isfile(os.path.join(script_path_in,request,"stop.iterating"))))
									# Check required service name uniqueness (Just a precaution, as the request name- which should also be the service name- must be unique when the user made the request)
									service_name = self.checkSerName(ser=ser, iter_no=ser_it, client=client)
									if not service_name:
										flog.write("Error: Another service with the same name, " + service_name + ", exists at " + str(time.time()) + "\n")
										# TODO: move to failed. In the future, another service name should be generated if desired
										break
									
									# Check that user required images are allowed by VIFI Node
									docker_img = self.checkServiceImage(conf['domains']['sets'][dset]['docker']['docker_img'], conf_in['services'][ser]['image'])
									if not docker_img:
										flog.write('Error: Wrong container images specified by end-user. Please, select one from ' + str(conf['domains']['sets'][dset]['docker']['docker_img']) + " for request " + request + " at " + str(time.time()) + "\n")
										# TODO: move to failed
										break
									
									# Check all user required data can be mounted in user required mode (e.g., write mode)
									if not self.checkDataOpt(conf, conf_in):
										flog.write('Error: Wrong data mounting options specified by end-user for request ' + request + " at " + str(time.time()) + "\n")
										# TODO: move to failed
										break
									
									# Check all files are satisfied for current service. Otherwise, move to the next service
									if not self.checkInputFiles(os.path.join(script_path_in, request), conf_in['services'][ser]['dependencies']['files']):
										flog.write("Error: Some or all required files are missed for " + request + " at " + str(time.time()) + "\n")
										# TODO: if this situation continues, then move to failed
										continue
									
									# Check all preceding services are complete, or the preceding service(vifi_server) reached the required status, before running the current service
									if not self.checkSerDep(servs=servs, ser_name=service_name, user_conf=conf_in):
										flog.write("Error: Some or all preceding services are missed for " + request + " at " + str(time.time()) + "\n")
										# TODO: if this situation continues, then move to failed
										continue
									
									# Check if other precedence conditions (e.g., functions) are satisfied before running current service. Otherwise, move to next request
									if not self.checkFnDep(conf_in):
										flog.write("Error: Some or all precedence functions are missed for " + request + " at " + str(time.time()) + "\n")
										# TODO: if this situation continues, then move to failed
										continue
									
									# Check available task number for current service (VIFI Node can limit concurrent number of running tasks for one service)
									task_no = self.setServiceNumber(docker_rep=docker_rep, user_rep=conf_in['services'][ser]['tasks'])  # set_i number of service tasks to allowed number
									if task_no != conf_in['services'][ser]['tasks']:
										flog.write("Warning: Number of tasks for service " + service_name + " in request " + str(request) + " will be " + str(task_no) + " at " + str(time.time()) + "\n")
										
									# Check time threshold to check service completeness
									ser_ttl = self.setServiceThreshold(ser_check_thr, conf_in['services'][ser]['ser_check_thr'])  # set_i ttl to allowed value
									if ser_ttl != conf_in['services'][ser]['ser_check_thr']:
										flog.write("Warning: Service check threshold for request " + str(request) + " will be " + str(ser_ttl) + " at " + str(time.time()) + "\n")
									
									# Create the required containerized user service, add service name to internal list of services of current request, and log the created service
									# TOOO: Currently, the created service is appended to an internal list of service. In the future, we may need to keep track of more parameters related to the created service (e.g., user name, request path, ... etc)
									try:
										if self.createUserService(client=client, service_name=service_name, docker_rep=task_no, \
														script_path_in=script_path_in, request=request, \
														container_dir=conf_in['services'][ser]['container_dir'], data_dir=data_dir, \
														user_data_dir=conf_in['services'][ser]['data'], work_dir=conf_in['services'][ser]['work_dir'], script=conf_in['services'][ser]['script'], \
														docker_img=docker_img, docker_cmd=conf_in['services'][ser]['cmd_eng'], \
														user_args=conf_in['services'][ser]['args'], user_envs=conf_in['services'][ser]['envs'], user_mnts=conf_in['services'][ser]['mnts'], ttl=ser_ttl, \
														user=docker_user, groups=docker_groups):
											ser_start_time = time.time()  # Record service creation time
											self.req_list[request]['services'][service_name] = {'tasks':task_no}
											self.req_list[request]['services'][service_name]['start'] = ser_start_time
											flog.write(repr(ser_start_time) + ":" + str(client.services.get(service_name)) + "\n")  # Log the command
											
											# Update central middleware log if required
											mes = {'request':request, 'service':service_name, 'tasks':task_no, 'start':ser_start_time}
											self.logToMiddleware(middleware_conf=conf['middleware']['log'], body=mes)
										else:
											flog.write("Error: Could not create service " + service_name + ": \n")
											traceback.print_exc(file=flog)
										
									except:
										flog.write("Error: occurred while launching service " + service_name + ": \n")
										traceback.print_exc(file=flog)
											
									# Check completeness of created service to transfer results (if required) and to end service
									if self.checkServiceComplete(client, service_name, int(task_no), int(ser_ttl)):
										# Log completeness time
										# print('DEBUG: after service complete, iteration: '+str(servs[ser]['cur_iter'])+', stop: '+str(os.path.isfile(os.path.join(script_path_in,request,"stop.iterating"))))
										ser_end_time = time.time()
										self.req_list[request]['services'][service_name]['end'] = ser_end_time
										self.req_list[request]['services'][service_name]['status'] = 'succeed'
										flog.write("Finished service " + service_name + " for request " + request + " at " + repr(ser_end_time) + "\n\n")
										
										# Update central middleware log if required
										mes = {'request':request, 'service':service_name, 'end':ser_end_time, 'status':'succeed'}
										self.logToMiddleware(middleware_conf=conf['middleware']['log'], body=mes)
										
										# Move/Copy (or other required sequence of actions) required results, if any, to specified destinations
										if conf_in['services'][ser]['results']:
											self.actOnResults(conf=conf_in['services'][ser]['results'], res_cur_dir=script_processed, res_dest_dir=os.path.join(script_processed, req_res_path_per_request))
										
										# Remove list of files/directories (if exist) that should be updated before the new service (iteration) starts. These files/directories are dependencies for the next service (iteration), and if they are not removed, then the new service (iteration) will start with the outdated data
										if conf_in['services'][ser]['toremove']:
											self.toRemove(conf=conf_in['services'][ser]['toremove'], data_path=script_processed)
											
										# Update service status, request status, and request configuration file
										tmp_ser_stat = True
										servs[ser]['cur_iter'] += 1
										conf_in['services'][ser]['iterative']['cur_iter'] += 1
										self.dump_conf(conf_in, os.path.join(script_path_in, request, conf_file_name), flog)
										
										# Delete service, if required, to release resource
										try:
											# TODO: Deleted or finished services should be recorded (either in a local list/dict, or in the user configuration file). Thus, it will be known which services, or service iterations, have finished  
											self.delService(client, service_name, str(conf['domains']['sets'][dset]['terminate']))
										except:
											flog.write("Error: failed to delete service " + service_name + " at " + repr(time.time()) + "\n")
											continue
										
										# Create metadata log file, if required, in the finished directory to be sent with the rest of results. This file contains useful information for the receiving VIFI Node
										self.createMetadata()

										# Make a UUID to identify the compressed results that will be transfered (useful for log tracing)
										res_uuid = str(uuid.uuid1())
											
										# IF S3 IS ENABLED, THEN TRANSFER REQUIRED RESULT FILES TO S3 BUCKET
										if self.checkTransfer(conf_in['services'][ser]['s3']['transfer'], servs, ser, os.path.join(script_path_in, request), flog) and conf_in['services'][ser]['s3']['results'] and conf_in['services'][ser]['s3']['bucket'] :  # s3_transfer is True and there are specified results to transfer, if exist, and s3_buc has some value
											self.s3Transfer(conf_in['services'][ser]['s3'], \
														os.path.join(script_processed, req_res_path_per_request))
											mes_time = time.time()
											flog.write("Transfered to S3 bucket at " + repr(mes_time) + "\n")
											self.req_list[request]['services'][service_name]['s3'] = {'sent':mes_time}
											
											# Update central middleware log if required
											mes = {'request':request, 'service':service_name, 's3':{'sent':mes_time}}
											self.logToMiddleware(middleware_conf=conf['middleware']['log'], body=mes)
										
										# If NIFI(s) is(are) enabled, then transfer required results using NIFI
										if 'nifi' in conf_in['services'][ser]:
											self.req_list[request]['services'][service_name]['nifi'] = []
											for nifi_sec in conf_in['services'][ser]['nifi']:
												if self.checkTransfer(nifi_sec['transfer'], servs, ser, os.path.join(script_path_in, request), flog) and nifi_sec['results']:
													res_name = self.nifiTransfer(user_nifi_conf=nifi_sec, \
																	data_path=os.path.join(script_processed, req_res_path_per_request), \
																	res_id=res_uuid, pg_name=dset, \
																	tr_res_temp_name='tr_res_temp')
													if res_name:
														# NIFI transfer succeeded 
														mes_time = time.time()
														flog.write("Intermediate results " + res_name + " transfer by NIFI succeeded at " + repr(mes_time) + "\n")
														self.req_list[request]['services'][service_name]['nifi'].append({'sent':mes_time, 'res_file':os.path.basename(res_name), 'destination':{'ip':nifi_sec['target_uri'], 'set':nifi_sec['target_remote_input_port']}})
														# Update central middleware log if required
														mes = {'request':request, 'service':service_name, 'nifi':{'sent':mes_time, 'res_file':os.path.basename(res_name)}}
														self.logToMiddleware(middleware_conf=conf['middleware']['log'], body=mes)
													else:
														# NIFI transfer failed
														flog.write("Intermediate results " + res_name + " transfer by NIFI failed at " + repr(time.time()) + "\n")
														# TODO: should the user request be terminated? or just continue with future service(vifi_server)
												
										# If SFTP is enabled, then transfer required results using SFTP
										if 'sftp' in conf_in['services'][ser]:
											self.req_list[request]['services'][service_name]['sftp'] = []
											for sftp_sec in conf_in['services'][ser]['sftp']:
												if self.checkTransfer(sftp_sec['transfer'], servs, ser, os.path.join(script_path_in, request), flog) and sftp_sec['results']:
													res_sftp = self.sftpTransfer(user_sftp_conf=sftp_sec, \
																	data_path=os.path.join(script_processed, req_res_path_per_request))
													if res_sftp:
														# sftp transfer succeeded 
														mes_time = time.time()
														self.req_list[request]['services'][service_name]['sftp'].append({'sent':mes_time,'sftp_server':sftp_sec['host']})
														flog.write("Transfer to SFTP Server succeeded at " + repr(mes_time) + "\n")
														
														# Update central middleware log if required
														mes = {'request':request, 'service':service_name, 'sftp':{'sent':mes_time,'sftp_server':sftp_sec['host']}}
														self.logToMiddleware(middleware_conf=conf['middleware']['log'], body=mes)
														
													else:
														# sftp transfer failed
														flog.write("Transfer to SFTP Server "+str(sftp_sec['host'])+" failed at  " + repr(time.time()) + os.linesep)
														
									else:
										# Service failed
										tmp_ser_stat = False
										break	
									
									# print('DEBUG: tmp_ser_stat: '+str(tmp_ser_stat))
									
									# Update service iteration number
									ser_it += 1
									
								if not tmp_ser_stat:
									# TODO: If current service fails, then abort whole request. This behavior may need modifications in the future
									mes_time = time.time()
									self.req_list[request]['services'][service_name]['status'] = 'failed'
									self.req_list[request]['services'][service_name]['end'] = mes_time
									flog.write("Failed service " + service_name + " for request " + request + " at " + repr(mes_time) + "\n\n")
									
									# Update central middleware log if required
									mes = {'request':request, 'service':service_name, 'status':'failed', 'end':mes_time}
									self.logToMiddleware(middleware_conf=conf['middleware']['log'], body=mes)
									
								# Update request status according to current service status, and abort request if any service fails
								final_req_stat = final_req_stat and tmp_ser_stat
								# print('DEBUG: final_req_stat: '+str(final_req_stat))
								if not final_req_stat:
									break
							
							# Record request end time and update internal request dictionary
							req_end_time = time.time()
							self.req_list[request]['end'] = req_end_time
							
							# Update 'curserv' (i.e., current service) in request configuration file to indicate that all services have been processed
							conf_in['curserv']='post_services'
							self.dump_conf(conf_in, os.path.join(script_path_in, request, conf_file_name), flog)
							
							# Update central middleware log if required
							mes = {'request':request, 'end':req_end_time}
							self.logToMiddleware(middleware_conf=conf['middleware']['log'], body=mes)
							
							# Move finished request to successful requests path, or to failed otherwise. Update internal requests dictionary accordingly
							if final_req_stat:
								shutil.move(script_processed, script_finished)
								self.req_list[request]['status'] = 'success'
								flog.write("Request " + request + " finished at " + repr(req_end_time) + "\n")
								
								# Update central middleware log if required
								mes = {'request':request, 'status':'success'}
								self.logToMiddleware(middleware_conf=conf['middleware']['log'], body=mes)
								
								# Create metadata log file, if required, in the finished directory to be sent with the rest of results. This file contains useful information for the receiving VIFI Node
								self.createMetadata()
								
								# Move final results to final destination
								if conf_in['fin_dest']['transfer']:
									
									# Make a UUID to identify the compressed results that will be transfered (useful for log tracing)
									res_uuid = str(uuid.uuid1())
									
									# IF S3 IS ENABLED, THEN TRANSFER REQUIRED RESULT FILES TO S3 BUCKET
									if conf_in['fin_dest']['s3']['transfer'] and conf_in['fin_dest']['s3']['bucket']:  # s3_transfer is True and s3_buc has some value
										self.s3Transfer(conf_in['fin_dest']['s3'], os.path.join(script_finished, req_res_path_per_request))
										flog.write("Transfered final results to S3 bucket at " + repr(time.time()) + "\n")
									
									# If SFTP is enabled, then transfer required results using SFTP 
									if conf_in['fin_dest']['sftp']['transfer']:
										res_sftp = self.sftpTransfer(user_nifi_conf=conf_in['services'][ser]['sftp'], \
														data_path=os.path.join(script_finished, req_res_path_per_request))
										if res_sftp:
											# sftp transfer succeeded 
											mes_time = time.time()
											self.req_list[request]['sftp'] = {'sent':mes_time}
											flog.write("Transfer final results to SFTP Server succeeded at " + repr(mes_time) + "\n")
											
											# Update central middleware log if required
											mes = {'request':request, 'sftp':{'sent':mes_time}}
											self.logToMiddleware(middleware_conf=conf['middleware']['log'], body=mes)
										else:
											# sftp transfer failed
											flog.write("Transfer final results to SFTP Server failed at  " + repr(mes_time) + "\n")
												
									# If NIFI is enabled, then transfer required results using NIFI 
									if conf_in['fin_dest']['nifi']['transfer']:
										res_name = self.nifiTransfer(user_nifi_conf=conf_in['fin_dest']['nifi']['transfer'], \
															data_path=os.path.join(script_finished, req_res_path_per_request), \
															res_id=res_uuid, pg_name=dset, \
															tr_res_temp_name='tr_res_temp')
										if res_name:
											# Wait for the transfer to be done
											mes_time = time.time()
											flog.write("Final results " + res_name + " transfer by NIFI succeeded at " + repr(mes_time) + "\n")
											self.req_list[request]['nifi'] = {'sent':mes_time}
											
											# Update central middleware log if required
											mes = {'request':request, 'nifi':{'sent':mes_time}}
											self.logToMiddleware(middleware_conf=conf['middleware']['log'], body=mes)
										else:
											# Final results transfer by NIFI failed
											flog.write("Final results " + res_name + " transfer by NIFI failed at " + repr(time.time()) + "\n")
							else:
								shutil.move(script_processed, script_failed)
								mes_time = time.time()
								self.req_list[request]['status'] = 'failed'
								flog.write("Request " + request + " FAILED at " + repr(mes_time) + "\n")
								
								# Update central middleware log if required
								mes = {'request':request, 'status':'failed'}
								self.logToMiddleware(middleware_conf=conf['middleware']['log'], body=mes)
								
							# Write the request log
							self.reqLog(req_log_path=self.vifi_conf['req_log_path'], req_log=self.req_list[request], req=request + '.' + str(uuid.uuid1()) + '.log.yml')
							
							# Clean the request log to save resource
							del self.req_list[request]
								
				else:
					print('Error: Specified set_i ' + dset + ' does not exist')
		except:
			result = 'Error: "vifiRun" function has error(vifi_server): '
			if flog:
				flog.write(result)
				traceback.print_exc(file=flog)
			else:
				print(result)
				traceback.print_exc()
		finally:
			if flog:
				flog.close()
	
	def vifiRunLoop(self, sets:List[str]=None, request_in:List[str]=None, conf:dict=None, flog:TextIOWrapper=None) -> None:
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
					conf = self.vifi_conf
				else:
					print('Error: No VIFI server configuration exists')
					sys.exit()
					
			while not self.stop:
				self.vifiRun(sets, request_in, conf)
				time.sleep(conf['domains']['proc_int'])
		except:
			result = 'Error: "vifiRunLoop" function has error(vifi_server): '
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
		
		# Parse input arguments
		parser = argparse.ArgumentParser()
		parser.add_argument('--sets', nargs='*', help='List of sets to be processed', default=None)  # List of sets to be processed
		parser.add_argument('--vifi_conf', help='VIFI configuration file for current instance of VIFI server', default='vifi_config.yaml')  # List of sets to be processed
		parser.add_argument('--mprocess', help='Run VIFI in multiprocessing mode if yes. "No" is useful for debugging', default='yes')  # Run VIFI in multiprocessing mode if yes. "No" is useful for debugging
		arguments = parser.parse_args()
		mp=str.lower(arguments.mprocess)
		
		if mp=='yes':	# Run VIFI in multiprocessing mode
			logger = multiprocessing.log_to_stderr()
			# logger.setLevel(logging.INFO)
			# logger.warning('doomed')
			logger.setLevel(logging.DEBUG)
	
			# Create a VIFI server instance (Created by BaseManager to be shared between processes)
			BaseManager.register('vifi', vifi)
			m = BaseManager()
			m.start()
			s = m.vifi(arguments.vifi_conf)
			
			# Create list of processes to run different VIFI functionalities
			p = []
			p.append(Process(target=s.unpackCompressedRequestsLoop, kwargs={'sets':arguments.sets}))
			p.append(Process(target=s.vifiRunLoop, kwargs={'sets':arguments.sets}))
			
			# Run the created VIFI processes
			for i in p:
				i.start()
	
			# Keep running VIFI server till receiving a STOP request 
			while True:
				lines = select.select([sys.stdin], [], [], 1)[0]
				if 'stop' in [x.readline().strip().lower() for x in lines]:
					p1 = Process(target=s.end)
					p1.start()
					p1.join()
					break
			for i in p:
				i.join()
			p.clear()
			
		else:	# Run VIFI in a single main process. Useful for debugging
			while True:
				v=vifi(arguments.vifi_conf)
				v.unpackCompressedRequests(sets=arguments.sets)
				v.vifiRunLoop(sets=arguments.sets)
				time.sleep(1)
			
			
				
