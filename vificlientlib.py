from flask import Flask, request
from flask_restful import Api, Resource, reqparse
import yaml, os, traceback
from _io import TextIOWrapper
from jinja2.lexer import Failure
from pip._internal.cli.status_codes import SUCCESS

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
    
    if reqargs and 'path' in reqargs and os.path.isfile(reqargs['path']):   # Load user configuration file from specified path
        conf={successRequestKey:load_conf(reqargs['path'])}
    elif os.path.isfile("conf.yml"):    # If no path is specified for user configuration file, then set path to default location which is 'conf.yml'
        conf={successRequestKey:load_conf("conf.yml")}
    else:
        conf={failureRequestKey:'Could not find user configuration file'}
    
    return conf

def getServices(reqargs:dict,flog:TextIOWrapper=None)->dict:
    ''' Return configurations for all services in the specified configuration.
    @param reqargs: Request arguments
    @type reqargs: dict
    @param flog: Log file to record raised events
    @type flog: TextIOWrapper (file object) 
    @return: Services configuration
    @rtype: dict 
    '''
    
    conf=getConfFromReqArgs(reqargs)
    if successRequestKey in conf:
        conf=conf[successRequestKey]
        if 'services' in conf:
            return {successRequestKey:conf['services']}
        else:
            return {failureRequestKey:'Could not find any service in the specified user configuration file'}
    else:
        return conf
    
def getService(reqargs:dict,ser:str,flog:TextIOWrapper=None)->dict:
    ''' Return configuration of specified service if exists.
    @param reqargs: Request arguments
    @type reqargs: dict
    @param ser: Required service to be extracted from configuration
    @type ser: str
    @param flog: Log file to record raised events
    @type flog: TextIOWrapper (file object) 
    @return: Service configuration
    @rtype: dict  
    '''
    
    services=getServices(reqargs)
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
    
    ser=getService(reqargs)
    if successRequestKey in ser:
        if 'nifi' in ser:
            return ser['nifi']
        else:
            return {failureRequestKey:'Could not find NiFi transfers for the specified service'}
    else:
        return ser

class User(Resource):

    def get(self, name):
        if name.lower()=='conf':    # The user is asking for the whole configuration file
            conf=getConfFromReqArgs(request.args)
            if failureRequestKey not in conf:
                return conf, 200
            return "User configuration file not found", 404
        
        
        elif name.lower()=='services':  # Return all services in the user configuration file
            services=getServices(request.args)
            if successRequestKey in services:
                return services[successRequestKey], 200
                if services:
                    return services, 200
                return "User coniguration has no services",404
            return "User configuration file not found", 404
        
        elif name.lower()=='service': # Return specific service configuration
            conf=getConfFromReqArgs(request.args)
            if conf:
                services=getServices(conf)
                if services:
                    if 'service' in request.args:
                        serv=getService(conf, request.args['service'])
                        if serv:
                            return serv, 200
                        return "The specified service not founud",404
                    return "No service has been specified. Please specify a service and try again", 404
                return "User coniguration has no services",404
            return "User configuration file not found", 404
        
        elif name.lower()=='nifi_transfers':    # The user is asking for the nifi destinations associated with a specific service, or all services if no service is specified
            conf=getConfFromReqArgs(request.args)
            if conf:
                services=getServices(conf)
                if services:
                    if 'service' in request.args:
                        serv=getService(conf, request.args['service'])
                        if serv:
                            nifitransfers=getNiFiTransfers(serv)
                            if nifitransfers:
                                return nifitransfers, 200
                            return "Specified service has no nifi transfers", 404
                        return "The specified service not founud",404
                    return "No service has been specified. Please specify a service and try again", 404
                return "User coniguration has no services",404
            return "User configuration file not found", 404

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
        if name.lower()=='changeAllNiFiTransfers':    # The user is asking to update the nifi destinations associated with a specific service
            conf=getConfFromReqArgs(request.args)
            if conf:
                services=getServices(conf)
                if services:
                    if 'service' in request.args:
                        serv=getService(conf, request.args['service'])
                        if serv:
                            nifitransfers=getNiFiTransfers(serv)
                            if not nifitransfers:
                                nifitransfer={}
                            if 'condition' in request.args:
                                nifitransfers['transfer']={'condition':request.args['condition']}
                                
                            return "Specified service has no nifi transfers", 404
                        return "The specified service not founud",404
                    return "No service has been specified. Please specify a service and try again", 404
                return "User coniguration has no services",404
            return "User configuration file not found", 404
        return user, 201

    def delete(self, name):
        global users
        users = [user for user in users if user["name"] != name]
        return "{} is deleted.".format(name), 200

      
api.add_resource(User, "/user/<string:name>")

if __name__ == '__main__':
    app.run(debug=True)
