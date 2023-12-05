# -*- coding: utf-8 -*-
"""
Created on Wed Nov 17 11:53:10 2021

@author: anton.freyberg
"""

from os import environ
import json
#import numpy as np
import re
import requests

dynToken = environ.get('DYN_API_TOKEN')
dynUrl = environ.get('DYN_API_URL')
dynPaasToken = environ.get('DYN_PAAS_TOKEN')



headers = {
    'Authorization': 'Api-Token {}'.format(dynToken)
}

#header needed for put request
headersPUT = {
    'Authorization': 'Api-Token {}'.format(dynToken),
    'Content-Type': 'application/json'
}

headersPaas = {
    'Authorization': 'Api-Token {}'.format(dynPaasToken)
}


#check if versions given by the User are correct
def checkVersions(version, versionList):
    
    if version in versionList:
        return 1
    else:
        print("This version is not available \n")
        return 0
    

#get the versions available in the environment and sort them
def getAvailableVersions(osType):
    query = {}
    req = requests.get ("{}/api/v1/deployment/installer/agent/versions/{}/default".format(dynUrl, osType), params=query, headers=headersPaas)
    response = req.json()
    versions = response['availableVersions']
    
    #versionToBeUpdated = re.search ('\d{8}', versionToBeUpdated).group()
    timestamps = [re.search ('\d{8}', i).group() for i in versions]    
    timespamps, versions = zip(*sorted(zip(timestamps, versions)))
    
    return versions
    
#get OS types in the environment
def getOsTypes():
    
    query = {     'pageSize': 1000,
                  'entitySelector': 'type("HOST"),state("RUNNING")',
                  'fields': 'properties.osType',
                  'from': '-1w',
                  'to': 'now'}
    req = requests.get ("{}/api/v2/entities".format(dynUrl), params=query, headers=headers)
    response = req.json()
    entities = response['entities']
    osType = set([entity['properties']['osType'] for entity in entities])
    
    return osType

#get agent versions in the environment for a specific osType
def getAgentVersion(osType):
    
    query = {     'pageSize': 1000,
                  'entitySelector': 'type("HOST"),state("RUNNING"),osType("{}")'.format(osType),
                  'fields': 'properties.installerVersion, properties.osType',
                  'from': '-1w',
                  'to': 'now'}
    req = requests.get ("{}/api/v2/entities".format(dynUrl), params=query, headers=headers)
    response = req.json()
    entities = response['entities']
    
    #entityId = [entity['entityId'] for entity in entities]
    
    
    installerVersion = set([entity['properties']['installerVersion'] for entity in entities])
    
    return installerVersion
    

#Choose the hosts to be update based on version and osType
def getHostListToBeUpdated(version, osType):
    query = {     'pageSize': 1000,
                  'entitySelector': 'type("HOST"),state("RUNNING"),installerVersion("{}"),osType ("{}"),isMonitoringCandidate("false")'.format(version,osType),
                  'fields': 'properties.installerVersion',
                  'from': '-1w',
                  'to': 'now'}
    req = requests.get ("{}/api/v2/entities".format(dynUrl), params=query, headers=headers)
    if req.status_code != 200:
        print (req.status_code, req.content)
        return 0
    response = req.json()

    entities = response['entities']
    entityId = [entity['entityId'] for entity in entities]

    return entityId
    

#update agents based on host entityID list
def updateSelectedAgents(hostIdList, version):
    
    
    for hostId in hostIdList:
        query = { "setting": "DISABLED",
                  "version": "{}".format(version) }
        req = requests.put ("{}/api/config/v1/hosts/{}/autoupdate".format(dynUrl, hostId), data=json.dumps(query), headers=headersPUT)

        if req.status_code != 204:
            print (req.status_code, req.content)
            return req.status_code, req.content
        
    return 0


#validate update call
def updateSelectedAgentsValidator(hostIdList, version):
    
    
    for hostId in hostIdList:
        query = { "setting": "DISABLED",
                  "version": "{}".format(version) }
        req = requests.post ("{}/api/config/v1/hosts/{}/autoupdate/validator".format(dynUrl, hostId), data=json.dumps(query), headers=headersPUT)

        if req.status_code != 204:
            print(req.content())
            return 0
        
    return 1


def userInteractionIntro():
    print("This script automates OneAgent updates. \n It works in 3 steps: \n")
    print("1.You need to choose the operating system of the hosts to be upgraded \n")
    print("2.You need to choose the hosts you want to update. We choose them by version. So e.g. we update all host with the OS chosen in 1. and with version 1.220. to version 1.225 \n")
    print("3.You need to choose the version you want to upgrade the hosts to. \n")


def userInterActionChooseOsType():
    osTypes = getOsTypes()
    print( "Please choose which operating system the hosts you want to update have. You have the following operating systems in your environment:")
    print (*osTypes)
    osType = input ("Please enter one of the above: \n")
    
    return osType


def userInterActionChooseVersions(osType):
    
    installerVersions = getAgentVersion(osType)
    print("Your {} hosts have the following versions: \n".format(osType))
    print(*installerVersions)
    if not installerVersions:
        print("No versions available")
        exit()
    
    versionToBeUpdated = input("Please enter the version that should be upgraded. The host with this version will be updated to a version you will choose in the next step. \n")
    if checkVersions(versionToBeUpdated, installerVersions) == 0:
        return
    
    hostListToBeUpdated = getHostListToBeUpdated(versionToBeUpdated, osType)
    if hostListToBeUpdated == 0:
        return
    
    print("The following hosts have version {}: \n".format(versionToBeUpdated))
    print(hostListToBeUpdated)
    print("\n")    
    #here we only show versions higher than the one chosen by the user .i.e. versionToBeUpdated
    availableVersions = getAvailableVersions(osType)
    print("These are the version available in your environment.: \n ")
    print(*availableVersions)
    versionToBeUpdatedTo = input( "Please enter the version you want to update your hosts to. It has to be HIGHER than the one you chose to upgrade: \n")
    if checkVersions(versionToBeUpdatedTo, availableVersions) == 0:
        return
    
    return hostListToBeUpdated, versionToBeUpdated, versionToBeUpdatedTo


def userInteractionConfirmUpdate(osType, hostListToBeUpdated,versionToBeUpdated, versionToBeUpdatedTo):
    confirmation = input("Are you sure you want to update the hosts from version " + str(versionToBeUpdated) + " to version " + str(versionToBeUpdatedTo )+"?\n [y/n]")
    confirmed = 0
    while confirmed == 0:
        if confirmation == "y":
            validate = updateSelectedAgentsValidator(hostListToBeUpdated, versionToBeUpdatedTo)
            confirmed = 1 
            #update
            if validate == 1:
                print ("The " + str(osType) +" hosts with version " + str(versionToBeUpdated) + " will now be updated to version " + str(versionToBeUpdatedTo ) )
                updateSelectedAgents(hostListToBeUpdated, versionToBeUpdatedTo)
            else:
                print ("Update failed. Reason: {}".format(validate))
                
            return 0
        
        elif confirmation == "n": 
            print ("Interrupted by user")
            confirmed = 1
        
        else:
            confirmation = input("Please enter y or n \n")
            confirmed = 0

    

    


def userInteraction():

    userInteractionIntro()
    osType = userInterActionChooseOsType()
    hostListToBeUpdated, versionToBeUpdated, versionToBeUpdatedTo = userInterActionChooseVersions(osType)
    userInteractionConfirmUpdate(osType, hostListToBeUpdated,versionToBeUpdated, versionToBeUpdatedTo)
    
    



if __name__ =='__main__':
    
    userInteraction()
    
    
    
    
    
    
    
    
    
    
    
    