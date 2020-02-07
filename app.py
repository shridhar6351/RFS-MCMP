# -*- coding: utf-8 -*-
#********************************************************************************
#Licensed Materials - Property of IBM
#5724-I68
#  
#© Copyright IBM Corp. 2018, 2019, 2020
#   
#US Government Users Restricted Rights - Use, duplication, or
#disclosure restricted by GSA ADP Schedule Contract with IBM Corp.  
#********************************************************************************

"""
 
  
Module Information
 * Module Name:      app.py
 * Title:            API's for the Airflow Adapter
 * Description:      This adapter acts as a bridge between MCMP and Airflow
 * Contributors:     Akhil Soni
"""


import flask
from flask import Flask
from flask import request
import requests
import json
import time
import boto3

app = Flask(__name__) 

#Sample Hello World route to check the flask server
@app.route('/')
def hello():
    return "Hello World!"

#result is a dictionary which maintains the data corresponding to every dag run in the form of a key value pair where key is the order number and the value is the status of the corresponding dag execution of the order number
result = {}
#inventory_data is a dictionary which maintains the data for the inventory in a key value pair where key is the order number and the value is the status of the corresponding dag execution of the order number but is currently being not used
inventory_data = {}

#The trigger_dag function is used to trigger various and appropriate dags based on the user input in the MCMP Store
def trigger_dag(x):
    #headers_af is the dictionary maintaing the headers required to make a POST API call to airflow
    headers_af = {
    'Cache-Control': 'no-cache',
    'Content-Type': 'application/json',
    }
    
    #response_af is the dictionary maintaining the response of the API call made to airflow to trigger dag.
    response_af = ""
    
    #The below block of code differentiates between a custom operation being performed and a order being submitted via Catalog
    if "custOps" in x:
        custOps = x["custOps"]
        if custOps == "change_instance_type": #checking which custom operation is being requested on the store inventory page
            tracking_id = x["tracking_id"]    #Storing the tracking_id
            cloud = x["cloud"]                #Storing cloud name, eg aws, azure, etc
            
            #data_af is a dictionary maintaining the parameters required for the dag
            data_af = '{"conf":{"orderNumber":' + f'"{tracking_id}"' + ',"cloud":' + f'"{cloud}"' + ',"instance_type":' + f'"{x["instance_type"]}"'  + ',"ip":' + f'"{x["ip"]}"'   + ',"InstanceId":' + f'"{x["InstanceId"]}"' + '}}'
            print(data_af)
            if cloud == "aws":
                response_af = requests.post('http://169.48.79.45:8080/api/experimental/dags/custOps_change_instance_type_aws/dag_runs', headers=headers_af, data=data_af)   
            print(response_af.text)
            
    #The below block of code differentiates when a dag is triggered to fetch the details for inventory but is currently not being used 
    if "serviceInstanceInfo" in x:
        tracking_id = x["serviceInstanceInfo"]["trackingInfo"]["trackingId"] 
        cloud = x["serviceInstanceInfo"]["trackingInfo"]["cloud"]
        data_af = '{"conf":{"orderNumber":' + f'"{tracking_id}"' + ',"cloud":' + f'"{cloud}"' + '}}'
        print(data_af)
        response_af = requests.post('http://169.48.79.45:8080/api/experimental/dags/fetch_VM_details_for_MCMP_Inventory/dag_runs', headers=headers_af, data=data_af)   
        print(response_af.text)
    
    #The below block of code differentiates when a dag is triggered on submission of a catalog item in MCMP Store
    if "serviceOfferingName" in x.keys():
        orderNumber=x["orderNumber"]
        if x["serviceOfferingName"] == "Provision AWS EC2 VM":  #Checking which catalog item is submitted
            host_name = x["configInfo"][0]["config"][0]["values"][0]["value"]
            instance_type = x["configInfo"][0]["config"][1]["values"][0]["value"]
            print(host_name)
            print(instance_type)
            data_af = '{"conf":{"orderNumber":' + f'"{orderNumber}"' + ',"host_name":' + f'"{host_name}"' + ',"instance_type":' + f'"{instance_type}"' + '}}'
            print(data_af)
            response_af = requests.post('http://169.48.79.45:8080/api/experimental/dags/provision_ec2_instance/dag_runs', headers=headers_af, data=data_af)
        if x["serviceOfferingName"] == "Install TomCat_Via_Ansible":  #Checking which catalog item is submitted
            host_name = x["configInfo"][0]["config"][0]["values"][0]["value"]
            instance_type = x["configInfo"][0]["config"][1]["values"][0]["value"]
            print(host_name)
            print(instance_type)
            data_af = '{"conf":{"orderNumber":' + f'"{orderNumber}"' + ',"host_name":' + f'"{host_name}"' + ',"instance_type":' + f'"{instance_type}"' + '}}'
            print(data_af)
            response_af = requests.post('http://169.48.79.45:8080/api/experimental/dags/provision_ec2_instance_and_install_tomcat/dag_runs', headers=headers_af, data=data_af)        
        print(response_af.text)
    return str(response_af.text)

#The below api is called when we drill down from the inventory page in MCMP Store   
@app.route('/serviceOfferingComponents', methods=['POST'])
def serviceOfferingComponents():
    print(request.json)
    x = request.json
    orderNumber = x["serviceInstanceInfo"]["trackingInfo"]["trackingId"]
    
    cloud = x["serviceInstanceInfo"]["trackingInfo"]["cloud"]
    if cloud == "aws":  #Fetch resource details from the respective cloud
        client = boto3.client("cloudformation", region_name="us-east-2",aws_access_key_id="AKIA2Z5VMZEAY3LNA3ZB" , aws_secret_access_key="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")
        StackName= "a" + str(orderNumber)
        Resources = [] #Stores list of resources in aws stack
        response = client.describe_stack_resources(StackName=StackName)
        print(response)
        stackId = response["StackResources"][0]["StackId"]
        for x in response["StackResources"]:
            Resources.append({"LogicalResourceId":x["LogicalResourceId"],"PhysicalResourceId":x["PhysicalResourceId"],"ResourceType":x["ResourceType"]})
        print(Resources)
        response = client.describe_stacks(StackName= StackName,NextToken="string")
        Outputs = response["Stacks"][0]["Outputs"]
        for Output in Outputs:
            if Output["OutputKey"] == "AZ":
                Availability_Zone = Output["OutputValue"]        
        
        ec2 = boto3.resource("ec2", region_name="us-east-2",aws_access_key_id="AKIA2Z5VMZEAY3LNA3ZB" , aws_secret_access_key="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")
        ids = []
        for x in Resources:  #Populate the resources list in the expected json format of MCMP
            Name = ""
            if x["LogicalResourceId"]=="EC2Instance":
                InstanceId = x["PhysicalResourceId"]
                print(InstanceId)
                ids.append(InstanceId)
                x["InstanceId"] = InstanceId
                for instance in ec2.instances.filter(InstanceIds=ids):
                    for tag in instance.tags:
                        if 'Name'in tag['Key']:
                            Name = tag['Value']
                            x["Name"] = Name
                    PublicIP = instance.public_ip_address
                    PrivateIP = instance.private_ip_address
                    InstanceType = instance.instance_type
                    LaunchTime = instance.launch_time
                    status = instance.state
                    if status["Name"]=="running":
                        state = "On"
                        x["state"] = state
                    elif status["Name"]=="stopped":
                        state = "Off"
                        x["state"] = state
                    x["templateOutputProperties"]=[]
                    x["templateOutputProperties"]=(
                         {"name":"Name","value":Name,"type":"string"},
                         {"name":"Public IP","value":PublicIP,"type":"string"},   
                         {"name":"Private IP","value":PrivateIP,"type":"string"},
                         {"name":"Availability Zone","value":Availability_Zone,"type":"string"},
                         {"name":"InstanceId","value":InstanceId,"type":"string"},
                         {"name":"Instance Type","value":InstanceType,"type":"string"}, 
                         {"name":"Launch Time","value":str(LaunchTime),"type":"string"}
                         )
            if x["LogicalResourceId"]=="InstanceSecurityGroup":
                client = boto3.client('ec2')
                group_name = x["PhysicalResourceId"]
                response = client.describe_security_groups(Filters=[dict(Name='group-name', Values=[group_name])])
                group_id = response['SecurityGroups'][0]['GroupId']
                security_group = ec2.SecurityGroup(group_id)
                group_id = security_group.group_id
                group_name = security_group.group_name
                group_description = security_group.description
                vpc_id = security_group.vpc_id
                x["templateOutputProperties"]=[]
                x["templateOutputProperties"]=(
                         {"name":"Group ID","value":group_id,"type":"string"},
                         {"name":"Group Name","value":group_name,"type":"string"},   
                         {"name":"Group description","value":group_description,"type":"string"},
                         {"name":"VPC ID","value":vpc_id,"type":"string"}
                         )
                x["state"] = "Active"    
                x["Name"] = Name            

#        print(Name,PublicIP,PrivateIP,Availability_Zone,InstanceId,InstanceType,LaunchTime)
        data_inv_new = {} #This dictionary is a key value pair with the value being list of resources
        list_resources = []
        for x in Resources:
            list_resources.append(
                {"resourceType":x["ResourceType"],
                "name":x["LogicalResourceId"],
                "providerName":"RFS", 
                "resourceId":x["PhysicalResourceId"],
                "templateOutputProperties":x["templateOutputProperties"],
                "status": x["state"],
                "connectInstruction": "You can connect to your instance using a remote desktop client of your choice (for Windows) or SSH client of your choice (for Linux). When prompted within that client, provide the appropriate username and connect using the following IP address: 34.80.171.47 ",
                "tags": 
                {
                    "Name": x["Name"],
                    "aws:cloudformation:logical-id": x["LogicalResourceId"],
                    "aws:cloudformation:stack-id": stackId,
                    "aws:cloudformation:stack-name": StackName,
                    "orderNumber": orderNumber
                }
                })

#        print(list_resources)  
        data_inv_new["resources"]=list_resources
        print(data_inv_new)  


    return json.dumps(data_inv_new)

#The below commented out code works with the above mentioned functions which are not being used currently(lines 68 to 75)
#     trigger_dag(x)
# #    print(x)
#     global inventory_data
#     inventory_data[orderNumber]=" "
#     while(inventory_data[orderNumber]==" "):
#         continue
#     return json.dumps(inventory_data[orderNumber])   

#The below API is called when a custom operation is performed from the MCMP Inventory page
@app.route('/executeOperation', methods=['POST'])
def templateOutputParams():
    x = request.json
    print(json.dumps(x))
    #headers dictionary contains the headers required to make the post call to the operation fulfilment queue
    headers = {
    'Apikey': 'c5079546-e117-5c48-9b7f-e36ebb743013',
    'Content-Type': 'application/json',
    'Username': 'akhil.soni1@gmail.com',
    }
    
    #Populating the json in the required format
    x = request.json
    a = "operation_fulfillment_response"
    teamId=x["teamId"]
    orderNumber=x["orderNumber"]
    operationRequestId=x["operationRequestId"]
    orderType=x["orderType"]
    version=x["version"]
    providerCode = x["providerCode"]
    trackingLink = "aaa"
    operationStatusTemplate = "aaa"
    #result[orderNumber] = "Dag " 
    data = '{\n    "routingKey":' + f'"{a}"' + ',\n    "messageContent":{\n  "teamId":' + f'"{teamId}"' + ',\n  "orderNumber":' + f'"{orderNumber}"' + ',\n  "operationRequestId":' + f'"{operationRequestId}"' + ',\n  "orderType":' + f'"{orderType}"' + ',\n  "version":' + f'"{version}"' +  ',\n  "operationTrackingInfo": {\n    "trackingLink":' + f'"{trackingLink}"' + ',\n    "operationStatusTemplate":' + f'"{operationStatusTemplate}"' + ',\n    "providerCode":' + f'"{providerCode}"' + '\n  }\n}\n}'
    print(data)
    cloud = "aws"
    custOps = "change_instance_type"
    data_af = {"tracking_id":orderNumber,"custOps":custOps,"cloud":cloud,"instance_type":x["configInfo"][0]["config"][0]["values"][0]["value"],"ip":x["resourceInfo"]["templateOutputProperties"][1]["value"],"InstanceId":x["id"]}
    
    #Calling the trigger_dag function with the required data to perform the custom operation
    trigger_dag(data_af)  
    
    #Calling the API to post to Operation Fulfilment Queue
    response = requests.post('https://myminikube.info:30091/message/OperationFulfillment', headers=headers, data=data, verify=False)

    global result
    result[orderNumber] = "Dag "

    return "Hi"

#The below API is called to update the status of the Custom Operation in MCMP Order Status Page
@app.route('/operationStatus', methods=['POST'])
def updateOperationStatus():
    x = request.json
    print(json.dumps(x))
    #headers dictionary contains the headers required to make the post call to the operation status queue
    headers = {
    'Apikey': 'c5079546-e117-5c48-9b7f-e36ebb743013',
    'Content-Type': 'application/json',
    'Username': 'akhil.soni1@gmail.com',
    }
    
    #Populating the json in the required format
    x = request.json
    a = "operation_status_response"
    teamId=x["teamId"]
    orderNumber=x["orderNumber"]
    operationRequestId=x["operationNumber"]
    orderType=x["orderType"]
    version=x["version"]
    providerCode = x["operationTrackingInfo"]["providerCode"]
    trackingLink = "aaa"
    operationStatusTemplate = "aaa"
    status = "ProvisionCompleted"
    data = '{\n    "routingKey":' + f'"{a}"' + ',\n    "messageContent":{\n  "teamId":' + f'"{teamId}"' + ',\n  "orderNumber":' + f'"{orderNumber}"' + ',\n  "operationNumber":' + f'"{operationRequestId}"' + ',\n  "orderType":' + f'"{orderType}"' + ',\n  "version":' + f'"{version}"' + ',\n  "status":' + f'"{status}"'  +  ',\n  "operationTrackingInfo": {\n    "trackingLink":' + f'"{trackingLink}"' + ',\n    "operationStatusTemplate":' + f'"{operationStatusTemplate}"' + ',\n    "providerCode":' + f'"{providerCode}"' + '\n  }\n}\n}'
    print(data)
    cloud = "aws"
    
    #result is updated by airflow. It is a global variable
    global result

    #Waiting for the result dictionary to be populated by airflow thus waiting for the status of the DAG
    while(result[orderNumber]=="Dag "):
        continue
     
    #Once the dag is completed, post the status to the operation status queue to update order status on the MCMP Order History Page
    response = requests.post('https://myminikube.info:30091/message/OperationStatus', headers=headers, data=data, verify=False)

    return "Hi"

#The below API is called when a user submits a catalog item from the MCMP Store page
@app.route('/provisioning', methods=['POST'])
def create_task():
    x = request.json
#    print(request.json)
    print(json.dumps(x))
    print("********************************************************************************************************")
    #headers dictionary contains the headers required to make the post call to the order fulfilment queue
    headers = {
    'Apikey': 'c5079546-e117-5c48-9b7f-e36ebb743013',
    'Content-Type': 'application/json',
    'Username': 'akhil.soni1@gmail.com',
    }
    #Populating the json in the required format
    a = "order_fulfillment_response"
    global result
    teamId=x["teamId"]
    orderNumber=x["orderNumber"]
    serviceFulfillmentId=x["serviceFulfillmentId"]
    orderType=x["orderType"]
    version=x["version"]
    result[orderNumber] = "Dag " 
    providerName=x["tags"]["providerName"]
    provider_type=x["tags"]["provider_type"]
    providerCode=x["tags"]["providerCode"]
    providerAccountRefId=x["tags"]["providerAccountRefId"]
    providerCredentialRefId=x["tags"]["providerCredentialRefId"]
    refId=x["tags"]["refId"]
    serviceInventoryId=x["tags"]["serviceInventoryId"]
    cloud = "aws"    
    data = '{\n    "routingKey":' + f'"{a}"' + ',\n    "messageContent":{\n  "teamId":' + f'"{teamId}"' + ',\n  "orderNumber":' + f'"{orderNumber}"' + ',\n  "serviceFulfillmentId":' + f'"{serviceFulfillmentId}"' + ',\n  "orderType":' + f'"{orderType}"' + ',\n  "version":' + f'"{version}"' + ',\n  "tags": {\n    "providerName":' + f'"{providerName}"' + ',\n    "provider_type":' + str(provider_type) + ',\n    "providerCode":' + f'"{providerCode}"' + ',\n    "providerAccountRefId":' + f'"{providerAccountRefId}"' + ',\n    "providerCredentialRefId":' + f'"{providerCredentialRefId}"' + ',\n    "refId":' + f'"{refId}"' + ',\n    "serviceInventoryId":' + f'"{serviceInventoryId}"' + '\n  },\n  "trackingInfo": {\n    "trackingId":'+ f'"{orderNumber}"' + ',\n  "cloud":' + f'"{cloud}"' + '\n  }\n}\n}'
    print(data)
    
    #Calling the trigger_dag function with the required data to perform the desired catalog item task
    response_af = trigger_dag(x)    
   
    #Calling the API to post to Order Fulfilment Queue
    response = requests.post('https://myminikube.info:30091/message/OrderFulfillment', headers=headers, data=data, verify=False)
    return "response"

@app.route('/status', methods=['POST'])
def submit_task():
    global result
    
    #headers dictionary contains the headers required to make the post call to the order status queue
    headers = {
    'Apikey': 'c5079546-e117-5c48-9b7f-e36ebb743013',
    'Content-Type': 'application/json',
    'Username': 'akhil.soni1@gmail.com',
    }
    #Populating the json in the required format
    a = "provisioning_status_response"
    x = request.json
    teamId=x["teamId"]
    orderNumber=x["orderNumber"]
    serviceFulfillmentId=x["serviceFulfillmentId"]
    orderType=x["orderType"]
    version=x["version"]
#    print(result[orderNumber])
    print("Hiiiiiiiiiiii")    
#    result[orderNumber] = "Dag " 
    print(result[orderNumber])
    providerName=x["tags"]["providerName"]
    provider_type=x["tags"]["provider_type"]
    providerCode=x["tags"]["providerCode"]
    providerAccountRefId=x["tags"]["providerAccountRefId"]
    providerCredentialRefId=x["tags"]["providerCredentialRefId"]
    refId=x["tags"]["refId"]
    serviceInventoryId=x["tags"]["serviceInventoryId"]
    cloud = "aws"
    data = '{\n    "routingKey":' + f'"{a}"' + ',\n    "messageContent":{\n  "teamId":' + f'"{teamId}"' + ',\n  "orderNumber":' + f'"{orderNumber}"' + ',\n  "serviceFulfillmentId":' + f'"{serviceFulfillmentId}"' + ',\n  "status": "ProvisionCompleted",\n  "comments": "comments error message",\n  "version":' + f'"{version}"' + ',\n  "tags": {\n    "providerName":' + f'"{providerName}"' + ',\n    "provider_type":' + str(provider_type) + ',\n    "providerCode":' + f'"{providerCode}"' + ',\n    "providerAccountRefId":' + f'"{providerAccountRefId}"' + ',\n    "providerCredentialRefId":' + f'"{providerCredentialRefId}"' + ',\n    "refId":' + f'"{refId}"' + ',\n    "serviceInventoryId":' + f'"{serviceInventoryId}"' + '\n  },\n  "trackingInfo": {\n    "trackingId":'+ f'"{orderNumber}"' + ',\n  "cloud":' + f'"{cloud}"' + '\n  }\n}\n}'
#    result[orderNumber] = "as"
    print(orderNumber)
    print(data)
    
    #Waiting for the result dictionary to be populated by airflow thus waiting for the status of the DAG
    while(result[orderNumber]=="Dag "):
        continue

    #Calling the API to post to Order Status Queue
    response = requests.post('https://myminikube.info:30091/message/ProvisioningStatus', headers=headers, data=data, verify=False)
    return "Hi"


@app.route('/dag_response_inventory', methods=['POST'])
def afdag_inventory_response():
    response=request.json
    print(response)
    global inventory_data
    orderNumber = response["orderNumber"]
    inventory_data[orderNumber]=response[orderNumber]
    print(response)
    return "dag inventory done"

@app.route('/dag_response', methods=['POST'])
def afdag_response():
    response=request.json
    print(response)
    global result 
    global inventory_data

    if "status" in response:
        orderNumber = response["orderNumber"]
        result[orderNumber] = "Dag " + response["status"]
    print(result)
    print("in dag response")
    return "dag response"
if __name__ == '__main__':
    app.run(host='0.0.0.0',port=9999)
