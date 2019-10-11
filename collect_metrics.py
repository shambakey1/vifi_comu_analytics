import os, yaml, json, argparse, csv, re


def extYAMLtoCSVlog(fin:str, fout:str):
    ''' Extract required logs in CSV format from YAML log files. Currently, the extracted information include, for each service in one request:
    - The service name
    - The service computation time in Seconds
    - The destination IP and port (i.e., set) of each service. As a service can have multiple destinations, each destination is written in one record
    - The result name that is sent to the specified destination IP and port
    - The transfer time of the result. If the transfer time shows a negative value that is close to zero, this is because recorded sent time is done after the recorded received time, and it is safe to assume the transfer time as zero 
    @param fin: Path and name of the YAML log file 
    @type fin: str
    @param fout: Path and name of the output CSV file
    @type fout: str 
    '''
    
    with open(fin, 'r') as f:
        res = yaml.load(f)
    
    l = []  # List of CSV results
    for s in res['services']:
        for n in res['services'][s]['nifi']:
            d = {}
            d['service_name'] = s
            d['service_comp_time(sec)'] = res['services'][s]['serv_comp_time']
            d['tasks'] = res['services'][s]['tasks']
            d['dest_ip'] = n['destination']['ip']
            d['dest_port'] = n['destination']['set']
            d['result'] = n['res_file']
            d['transfer_time(sec)'] = n['transfer_time']
            l.append(d)
    
    keys = l[0].keys()
    with open(fout, 'w') as f:
        dw = csv.DictWriter(f, keys)
        dw.writeheader()
        dw.writerows(l)


def completeLog(logs_parent_path:str, d:str) -> None:
    ''' Completes the YAML log file by calculating:
    - Each service computation time
    - Each result delivery and transfer time
    @param logs_parent_path: The root (i.e., parent) directory that contains logs sub-directories. Each log sub-directory represents a VIFI Node and must be named with the IP of this VIFI Node
    @type logs_parent_path: str
    @param d: Directory name that contains the YAML log file to be completed
    @type d: str
    '''
    
    # final_log=[]
    logfs = os.listdir(os.path.join(logs_parent_path, d))
    flog = ''  # YAML log file name
    for logf in logfs:
        # Search for the YAML log file under current log directory
        if '.yml' in logf or '.yaml' in logf:
            flog = os.path.join(logs_parent_path, d, logf)
            with open(flog) as f:
                l = yaml.load(f)
                break
                
    # Complete found YAML log if exists
    if flog:
        if 'req_comp_time' not in l or not l['req_comp_time']:
            l['req_comp_time'] = float(l['end']) - float(l['start'])
        for s in l['services']:
            itr = 0
            l['services'][s]['serv_comp_time'] = float(l['services'][s]['end']) - float(l['services'][s]['start'])
            for n in l['services'][s]['nifi']:
                f = os.path.join(logs_parent_path, re.search('//(.*):', n['destination']['ip'])[1], n['res_file'])
                with open(f, 'r') as ff:
                    fflog = json.load(ff)
                if 'deliverd_at' not in l['services'][s]['nifi'][itr] or not l['services'][s]['nifi'][itr]['deliverd_at']:
                    l['services'][s]['nifi'][itr]['deliverd_at'] = float(fflog['received_at']) / 1000  # NiFi records time in milli-sec. So, time record should be devided by 1000 as other time metrics are recorded by seconds
                if 'transfer_time' not in l['services'][s]['nifi'][itr] or not l['services'][s]['nifi'][itr]['transfer_time']:
                    l['services'][s]['nifi'][itr]['transfer_time'] = float(l['services'][s]['nifi'][itr]['deliverd_at']) - float(l['services'][s]['nifi'][itr]['sent'])
                itr += 1
        # final_log.append(l)
            
        with open(flog, 'w') as f:
            yaml.dump(l, f)
    else:
        print("No YAML log file was found under specified directory " + str(os.path.join(logs_parent_path, d)) + "\n")


# Parse input arguments
parser = argparse.ArgumentParser()
parser.add_argument('--root_logs_path', help='Root path of the logs directory')
parser.add_argument('--logs_dirs', nargs='+', help='List of directories, under root logs path, containing logs for each VIFI Node')  # usually, the value for this parameter is '35.167.35.244' '52.26.208.37' '52.32.117.160'

arguments = parser.parse_args()
logs_parent_path = arguments.root_logs_path  # Root path of the logs directory
dirs = arguments.logs_dirs  # List of directories, under the root logs path, containing logs for each VIFI Node

# Complete each YAML log file
for d in dirs:
    completeLog(logs_parent_path, d)
    # Extract required log information fromm YAML log file to a CSV file
    logfs = os.listdir(os.path.join(logs_parent_path, d))
    flog = ''  # YAML log file name
    for logf in logfs:
        # Search for the YAML log file under current log directory
        if '.yml' in logf or '.yaml' in logf:
            flog = os.path.join(logs_parent_path, d, logf)
            break
    extYAMLtoCSVlog(flog, os.path.join(logs_parent_path, d, 'summary.csv'))

