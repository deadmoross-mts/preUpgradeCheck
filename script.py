# function to parse lscpu command output
def lscpuParser(response):
    response = re.sub(' +',' ',response)
    responseList = response.split('\n')
    responseData = {}
    for each in responseList:
        if each != '':
            tempKey,tempVal = each.split(':')
            tempKey = tempKey.strip()
            tempVal = tempVal.strip()
            responseData[tempKey] = tempVal
        
    return(responseData)

# parse version data
def versionParser(config):
    config = config.replace('"','')
    config = config.replace("'",'')
    temp = config.split('=')
    temp0 = temp[0].rstrip()
    temp1 = temp[1].rstrip()
    return([temp0,temp1])

# the following function processes the response from df -BG command run on
# exactly one path
def processDfOutput(response):
    # process response
    # remove extra spaces
    labs,vals = re.sub(' +',' ',response).strip('\n').split('\n')
    # convert string to list
    labsTemp = labs.split(' ')
    # process the last value
    labsTemp[5] = labsTemp[5] + ' ' + labsTemp[6]
    del(labsTemp[6])
    # convert value string to list
    vals = vals.split(' ')
    # create a dictionary
    dfOutput = dict(zip(labsTemp,vals))
    
    return(dfOutput)

import subprocess
import re
from os import listdir
import csv
import datetime
import json

# minimum empty disk requirement
MINDISKSPACE = 8.0
# warn if disk is at or above below percentage
WARNINGATDISKUSE = 90.0
# critical MINIMUM major version to check for
CRITICALVERSION = 4
# maximum acceptable age of a backup in days
MAXBACKUPAGE = 6
# the minimum size of backup disk as a multiple of data disk
# e.g. 1.5 checks size(backup disk)/size(data disk) >= 1.5
MINBACKUPFACTOR = 1.5

# create output templates
# all clear = green
colGreen = '\x1b[6;30;42m' + '{}!' + '\x1b[0m'
# warning = red
colRed = '\x1b[6;30;41m' + '{}!' + '\x1b[0m'
# caution = orange
colOrange = '\x1b[6;30;43m' + '{}!' + '\x1b[0m'

# run the version check
# run bash command
output = subprocess.Popen(["cat /opt/alation/alation/opt/alation/django/main/alation_version.py"],stdout=subprocess.PIPE,shell=True)
# process response
response,val = output.communicate()
versionData = response.strip('\n').split('\n')

# find Alation major version number
for each in versionData:
    if "ALATION_MAJOR_VERSION" in each:
        majorVersion = int(each.split(' = ')[1])
    elif "ALATION_MINOR_VERSION" in each:
        minorVersion = int(each.split(' = ')[1])
    elif "ALATION_PATCH_VERSION" in each:
        patchVersion = int(each.split(' = ')[1])
    elif "ALATION_BUILD_VERSION" in each:
        buildVersion = int(each.split(' = ')[1])

version = str(majorVersion) + '.' + str(minorVersion) + '.' + str(patchVersion) + '.' + str(buildVersion)
        
if majorVersion >= CRITICALVERSION:
    print('Version > {} (current version = {}): '.format(CRITICALVERSION,version) + colGreen.format('OK'))
    versionFlag = True
else:
    print('Version > {} (current version = {}): '.format(CRITICALVERSION,version) + colRed.format('FAIL'))
    versionFlag = False

# check replication
# define commands
commands = "curl -L --insecure http://localhost/monitor/replication/"
# get response
process = subprocess.Popen('/bin/bash', stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
response, err = process.communicate(commands)
# process response
replicationMode = response.split('{')[1].split('}')[0].split(': ')[1].replace('"','')

# check replication criteria
if replicationMode == 'standalone':
    print('Replication mode standalone: ' + colGreen.format('OK'))
    replicationFlag = True
else:
    print(colRed.format('REPLICATION MODE NOT STANDALONE'))
    replicationFlag = False
    
# check if a minimum of 10GB space is free at /opt/alation/ by calling: df -h /opt/alation
# run bash command
output = subprocess.Popen(["df -BG /opt/alation"],stdout=subprocess.PIPE,shell=True)
# get response
response,val = output.communicate()
# get df readout
installDfOutput = processDfOutput(response)
# get remaining disk space
availSize = float(re.sub("\D", "", installDfOutput['Available']))
# check if there is at least 10 GB space available =
if availSize > MINDISKSPACE:
    print('Minimum 10GB disk space (available = {}GB): '.format(availSize) + colGreen.format('OK'))
    diskFlag = True
else:
    print('Minimum 10GB disk space (available = {}GB): '.format(availSize) + colRed.format('FAIL'))
    diskFlag = False

# check if disk is at least 90% full
usage = float(re.sub("\D", "", installDfOutput['Use%']))
if usage >= WARNINGATDISKUSE:
    print(colOrange.format('Caution! Disk is {}% full'.format(usage)))

# data and backup mount check
# run bash command for data drive
output = subprocess.Popen(["df -h $(cat /opt/alation/alation/.disk1_cache)"],stdout=subprocess.PIPE,shell=True)
# get response
dataResponse,val = output.communicate()
# get df readout
dataDfOutput = processDfOutput(dataResponse)

# run the bash command for backup drive
output = subprocess.Popen(["df -h $(cat /opt/alation/alation/.disk2_cache)"],stdout=subprocess.PIPE,shell=True)
# get response
backupResponse,val = output.communicate()
# get df readout
backupDfOutput = processDfOutput(backupResponse)

# ensure the mounting points are different for data and backup
if dataDfOutput['Mounted on'] != backupDfOutput['Mounted on']:
    mountFlag = True
    print('Data and backup on different mount: {}'.format(colGreen.format('OK')))
else:
    print('Data and backup on different mount: {}'.format(colRed.format('FAIL')))
    mountFlag = False

# ensure the storage devices are different for data and backup
if dataDfOutput['Filesystem'] != backupDfOutput['Filesystem']:
    storageFlag = True
    print('Data and backup on different device: {}'.format(colGreen.format('OK')))
else:
    storageFlag = False
    print('Data and backup on different device: {}'.format(colGreen.format('FAIL')))

# compare backup disk size and data disk size
backupToDataRatio = float(re.sub("\D", "", backupDfOutput['Size']))/float(re.sub("\D", "", dataDfOutput['Size']))

# check if backup disk is at least MINBACKUPFACTOR the size of data disk
if backupToDataRatio >= MINBACKUPFACTOR:
    print('Backup disk to data disk size ratio is at least {}: {}'.format(MINBACKUPFACTOR,colGreen.format('OK')))
else:
    print('Backup disk to data disk size ratio is {} which is lower than reccommended {}: {}'.format(backupToDataRatio,MINBACKUPFACTOR,colOrange.format('WARNING')))
    
# confirm backups
# get backup drive
with open('/opt/alation/alation/.disk2_cache','r') as f:
    loc = f.readline()

loc = loc.replace('\n','')
    
# read in backup files
backupFiles = listdir(loc+'/backup')

# extract the date information
backupDates = []
backupDTs = []
for each in backupFiles:
    temp = each.split('_')[0][:8]
    backupDates.append(temp)
    tempDt = datetime.datetime.strptime(temp,'%Y%m%d').date()
    backupDTs.append(tempDt)

# compute age of backups
today = datetime.date.today()

tDiff = []
diffRes = {}
for each in backupDTs:
    diff = int((today - each).days)
    tDiff.append(diff)
    diffRes[diff] = each

# get the newest backup
newestBackup = diffRes[min(tDiff)].strftime('%Y-%m-%d')
# check age of the backup
if len(backupDates) >= 1:
    if min(tDiff) <= MAXBACKUPAGE:
        print('Recent backup available (Last backup on: {}): {}'.format(newestBackup,colGreen.format('OK')))
        backupFlag = True
    else:
        print('No recent backup available. (Last backup on: {}, age: {}): {}'.format(newestBackup,str(min(tDiff)),colRed.format('FAIL')))
        backupFlag = False
else:
    print(colRed.format('WARNING! No backup found'))
    backupFlag = False


# extract CPU information
# run the bash command to get CPU information
output = subprocess.Popen(["lscpu"],stdout=subprocess.PIPE,shell=True)
# get response
cpuResponse,val = output.communicate()
# process response
lscpuOutput = lscpuParser(cpuResponse)

# get total memory information
output = subprocess.Popen(["grep MemTotal /proc/meminfo"],stdout=subprocess.PIPE,shell=True)
# get response
memResponse,val = output.communicate()
# process output
memResponse = lscpuParser(memResponse)

    
# parse out version data collected before
vDataTemp = list(map(lambda x: versionParser(x),versionData))
keys = list(map(lambda x: x[0],vDataTemp))
values = list(map(lambda x: x[1],vDataTemp))
fullLog = dict(zip(keys,values))

# add previously obtained data
fullLog['backupFiles'] = backupFiles
fullLog['Replication'] = replicationMode
fullLog['installDirDf'] = installDfOutput
fullLog['dataDirDf'] = dataDfOutput
fullLog['backupDirDf'] = backupDfOutput
fullLog['backupToDataRatio'] = backupToDataRatio
fullLog['cpuData'] = lscpuOutput
fullLog['totalMemory'] = memResponse.values()[0]

with open("/tmp/dataOutput.json", "w") as f:
    json.dump(fullLog,f)