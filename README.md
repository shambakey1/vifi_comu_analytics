# README #

This is the README for Virtual Information Fabric Infrastructure For Data-Driven Decisions from Distributed Data ([VIFI](http://vifi.uncc.edu)) project

### What is this repository for? ###

In today’s information age, data plays a pivotal role in many domains. VIFI offers a more effective solution to the traditional data fabric approach which will significantly reduce the time to conduct data analytics by:

* Providing a standard workflow with templates that can be customized
* Eases the time taken by data scientists to search, query and access data.

Current source code includes sample python files and xml templates as VIFI is still and test and development.

### How do I get set up? ###

As VIFI is open source project, all components are also open source. Current VIFI implementation assumes that:
## Each VIFI-node should have:

* Docker Swarm: Please refer to [Docker Swarm documentation](https://docs.docker.com/engine/swarm/) for installation and usage.
* [Apache NIFI](https://nifi.apache.org/): NIFI supports designing graphical data-operations workflows. Please refer to [NIFI documentation](https://nifi.apache.org/docs.html) for installation and usage.

## Directory Structure at each VIFI-Node
Each VIFI-node should have a "requests" folder that contains different directories for each use case (e.g., JPL directory for the earth science use case). Under each use case directory, the following directories exist:

* in: This directory keeps incoming requests from VIFI users to be processed by current use case workflow.
* finished: Upon successful completion of current VIFI request, results are moved to this directory. Each VIFI request has a separate folder under this "finished" directory.
* failed: Upon failure in processing current VIFI request, results are moved to a separate directory in this folder for further investigation.
* log: Keeps logging information of each VIFI request status (e.g., arrival, processing, success and failure)

### Contribution guidelines ###

VIFI follows a phased approach during devlopement. Thus, the more use cases we have, the more we learn to improve VIFI and identificy commoen requirements between different cases. Thus, we appreciate any use case that can benifit from VIFI.

### Who do I talk to? ###

* Repo owner or admin
* Other community or team contact