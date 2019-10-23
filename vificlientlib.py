from flask import Flask, request
from flask_restful import Api, Resource, reqparse
import yaml, os, traceback
from _io import TextIOWrapper

app = Flask(__name__)
api = Api(app)

failureRequestKey='Error' # This is the key of the returned response dictionary in case of failure
successRequestKey='Success' # This is the key of the returned response dictionary in case of success

def load_conf(infile:str, flog:TextIOWrapper=None) -> dict:
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
            return None
    except:
        result = 'Error: "load_conf" function has error(vifi_server): '
        if flog:
            flog.write(result)
            traceback.print_exc(file=flog)
        else:
            print(result)
            traceback.print_exc()

def getConfFromReqArgs(reqargs:dict,flog:TextIOWrapper=None) -> dict:
    ''' Loads the user configuration file based on request arguments, or loads the local configuration file if 
    request has no path argument.
    @param reqargs: Request arguments
    @type args: dict
    @param flog: Log file to record raised events
    @type flog: TextIOWrapper (file object) 
    @return: User configuration file as YAML object
    @rtype: dict
    '''
    
    if 'path' in reqargs:   # Load user configuration file from specified path
        if os.path.isfile(reqargs['path']):
            return {successRequestKey:load_conf(reqargs['path'])}
        else:
            return {failureRequestKey:'Could not find user configuration file at the specified path'}
    elif os.path.isfile("conf.yml"):    # If no path is specified for user configuration file, then set path to default location which is 'conf.yml'
        return {successRequestKey:load_conf("conf.yml")}
    else:
        return {failureRequestKey:'Could not find user configuration file'}

def getServices(reqargs:dict,flog:TextIOWrapper=None)->dict:
    ''' Return configurations for all services in the specified configuration.
    @param reqargs: Request arguments
    @type reqargs: dict
    @param flog: Log file to record raised events
    @type flog: TextIOWrapper (file object) 
    @return: Services configuration
    @rtype: dict 
    '''
    
    conf=getConfFromReqArgs(reqargs,flog)
    if successRequestKey in conf:
        conf=conf[successRequestKey]
        if 'services' in conf:
            return {successRequestKey:conf['services']}
        else:
            return {failureRequestKey:'Could not find any service in the specified user configuration file'}
    else:
        return conf
    
def getService(reqargs:dict,flog:TextIOWrapper=None)->dict:
    ''' Return configuration of specified service if exists.
    @param reqargs: Request arguments
    @type reqargs: dict
    @param flog: Log file to record raised events
    @type flog: TextIOWrapper (file object) 
    @return: Service configuration
    @rtype: dict  
    '''
    
    # Confirm that required service name is mentioned in the request arguments
    if 'service' in reqargs:
        ser=reqargs['service']
    else:
        return {failureRequestKey:'No service is specified in request arguments'}
    
    # Return required service if exists
    services=getServices(reqargs,flog)
    if successRequestKey in services:
        services=services[successRequestKey]
        if ser in services:
            return {successRequestKey:services[ser]}
        else:
            return {failureRequestKey:'Could not find specified service'}
    else:
        return services

def getNiFiTransfers(reqargs:dict,flog:TextIOWrapper=None)->dict:
    ''' Return NiFi tranfers of specified service if exists.
    @param reqargs: Request arguments including the service name to be retrieved
    @type reqargs: dict
    @param flog: Log file to record raised events
    @type flog: TextIOWrapper (file object) 
    @return: NiFi transfer configurations of specified service
    @rtype: List or dict  
    '''
    
    ser=getService(reqargs,flog)
    if successRequestKey in ser:
        ser=ser[successRequestKey]
        if 'nifi' in ser:
            return {successRequestKey:ser['nifi']}
        else:
            return {failureRequestKey:'Could not find NiFi transfers for the specified service'}
    else:
        return ser
    
def setNiFiTransferResults(reqargs:dict,flog:TextIOWrapper=None)->dict:
    ''' Change results sent to specified NiFi destination.
    @param reqargs: Request arguments including the service name to be retrieved
    @type reqargs: dict
    @param flog: Log file to record raised events
    @type flog: TextIOWrapper (file object) 
    @return: NiFi transfer configurations of specified service
    @rtype: List or dict  
    '''
    
    # Check if target argument is specified
    if 'target' in reqargs:
        target=reqargs['target']
    else:
        return {failureRequestKey:'No target NiFi is specified'}
    
    # Check if results argument is specified
    if 'results' not in reqargs:
        return {failureRequestKey:'No results are specified'} 
    
    # Check if results are specified in a list
    if not isinstance(reqargs['results'],list):
        return {failureRequestKey:'Results should be in a list'}
    
    # Extract all nifi transfers in the configuration file 
    nifitransfers=getNiFiTransfers(reqargs, flog)
    if successRequestKey in nifitransfers:
        nifitransfers=nifitransfers[successRequestKey]
        # Extract the nifi transfer with the specific target
        for nifitransfer in nifitransfers:
            if nifitransfer['target_uri']==target:
                nifitransfer['results']=reqargs['results']
                # Get the path of the configuration file
                if 'path' in reqargs:
                    path=reqargs['path']
                else:
                    path='conf.yml'
                # Update the configuration file
                with open(path,'r') as f:
                    conf=yaml.load(f)
                with open(path,'w') as f:
                    conf['services'][reqargs['service']]['nifi']=nifitransfers
                    yaml.dump(conf,f)   
                return {successRequestKey:'Results for nifi transfer with target '+reqargs['target']+' have been updated'}
        # If no nifi transfer exists with the specified target, then return an error
        return {failureRequestKey:'No nifi with the specified target exists'}    
    # Something went wrong in extracting nifi transfers. Just return the error    
    else:
        return nifitransfers

def setNiFiTransferCondition(reqargs:dict,flog:TextIOWrapper=None)->dict:
    ''' Change the transfer condition of the specified NiFi destination.
    @param reqargs: Request arguments including the service name to which NiFi transfer condition will be changed
    @type reqargs: dict
    @param flog: Log file to record raised events
    @type flog: TextIOWrapper (file object)
    @return: NiFi transfer configurations of specified service
    @rtype: List or dict  
    '''
    
    # Check if target argument is specified
    if 'target' in reqargs:
        target=reqargs['target']
    else:
        return {failureRequestKey:'No target NiFi is specified'}
    
    # Check if results argument is specified
    if 'condition' not in reqargs:
        return {failureRequestKey:'No conditions are specified'}
    
    # Extract all nifi transfers in the configuration file 
    nifitransfers=getNiFiTransfers(reqargs, flog)
    if successRequestKey in nifitransfers:
        nifitransfers=nifitransfers[successRequestKey]
        # Extract the nifi transfer with the specific target
        for nifitransfer in nifitransfers:
            if nifitransfer['target_uri']==target:
                nifitransfer['transfer']={'condition':reqargs['condition']}
                # Get the path of the configuration file
                if 'path' in reqargs:
                    path=reqargs['path']
                else:
                    path='conf.yml'
                # Update the configuration file
                with open(path,'r') as f:
                    conf=yaml.load(f)
                with open(path,'w') as f:
                    conf['services'][reqargs['service']]['nifi']=nifitransfers
                    yaml.dump(conf,f)   
                return {successRequestKey:'Condition for nifi transfer with target '+reqargs['target']+' has been updated'}
        # If no nifi transfer exists with the specified target, then return an error
        return {failureRequestKey:'No nifi with the specified target exists'}    
    # Something went wrong in extracting nifi transfers. Just return the error    
    else:
        return nifitransfers
    
def setNiFiTransfer(reqargs:dict,flog:TextIOWrapper=None)->dict:
    ''' Create/Change a NiFi sent to specified NiFi destination.
    @param reqargs: Request arguments including the service name to which NiFi will be changed/created
    @type reqargs: dict
    @param flog: Log file to record raised events
    @type flog: TextIOWrapper (file object) 
    @return: NiFi transfer configurations of specified service
    @rtype: List or dict  
    '''
    
    #TODO
    pass

class User(Resource):

    def get(self, name):
        if name.lower()=='conf':    # The user is asking for the whole configuration file
            conf=getConfFromReqArgs(request.get_json())
            if successRequestKey in conf:
                return conf[successRequestKey], 200
            else:
                return conf[failureRequestKey], 404
    
        elif name.lower()=='services':  # Return all services in the user configuration file
            services=getServices(request.get_json())
            if successRequestKey in services:
                return services[successRequestKey], 200
            else:
                return services[failureRequestKey], 404
        
        elif name.lower()=='service': # Return specific service configuration
            ser=getService(request.get_json())
            if successRequestKey in ser:
                return ser[successRequestKey], 200
            else:
                return ser[failureRequestKey],404
       
        elif name.lower()=='nifi_transfers':    # The user is asking for the nifi destinations associated with a specific service, or all services if no service is specified
            nifitransfers=getNiFiTransfers(request.get_json())
            if successRequestKey in nifitransfers:
                return nifitransfers[successRequestKey],200
            else:
                return nifitransfers[failureRequestKey],404

    def post(self, name):
        parser = reqparse.RequestParser()
        parser.add_argument("age")
        parser.add_argument("occupation")
        args = parser.parse_args()

        for user in users:
            if(name == user["name"]):
                return "User with name {} already exists".format(name), 400

        user = {
            "name": name,
            "age": args["age"],
            "occupation": args["occupation"]
        }
        users.append(user)
        return user, 201

    def put(self, name):
        if name.lower()=='changenifitransferresults':    # Change NiFi results submitted to specified destination
            res=setNiFiTransferResults(request.get_json())
            if successRequestKey in res:
                return res[successRequestKey], 201
            else:
                return res[failureRequestKey],404
        elif name.lower()=='changenifitransfercondition':    # Change NiFi results submitted to specified destination
            res=setNiFiTransferCondition(request.get_json())
            if successRequestKey in res:
                return res[successRequestKey], 201
            else:
                return res[failureRequestKey],404
        else:
            return 'No valid operation has been specified', 404        

    def delete(self, name):
        global users
        users = [user for user in users if user["name"] != name]
        return "{} is deleted.".format(name), 200

      
api.add_resource(User, "/user/<string:name>")

if __name__ == '__main__':
    app.run(debug=True)
