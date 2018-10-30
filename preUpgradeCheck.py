# ## Libraries and functions
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

# import libraries
import subprocess
import re
from os import listdir
import csv
import datetime
import json


# ## Configuration parameters
# config
# minimum empty disk requirement
MINDISKSPACE = 8.0
# warn if disk is at or above below percentage
WARNINGATDISKUSE = 90.0
# critical MINIMUM major version to check for
CRITICALVERSION = 4
# maximum acceptable age of a backup in days
MAXBACKUPAGE = 5
# the minimum size of backup disk as a multiple of data disk
# e.g. 1.5 checks size(backup disk)/size(data disk) >= 1.5
MINBACKUPFACTOR = 1.5
# mongoDB size requirements
MONGOx = 2

# create output templates
# all clear = green
colGreen = '\x1b[6;30;42m' + '{}!' + '\x1b[0m'
# warning = red
colRed = '\x1b[6;30;41m' + '{}!' + '\x1b[0m'
# caution = orange
colOrange = '\x1b[6;30;43m' + '{}!' + '\x1b[0m'
# summary object for the end
summary = []


# ## Version information check
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
    
# check major version requirement
if majorVersion >= CRITICALVERSION:
    print('Version > {} (current version = {}): '.format(CRITICALVERSION,version) + colGreen.format('OK'))
    summary.append('Version ({}) check passed: OK'.format(version))
    versionFlag = True
else:
    print('Version > {} (current version = {}): '.format(CRITICALVERSION,version) + colRed.format('FAIL'))
    versionFlag = False
    summary.append('Version ({}) check failed: FAIL'.format(version))

# check additional version information
if majorVersion <= 4:
    if minorVersion <= 10:
        flag410 = True
        print('{} Be sure to follow 4.10.x or below version specific steps here: https://alationhelp.zendesk.com/hc/en-us/articles/360011041633-Release-Specific-Update-Pre-Checks'.format(colOrange.format('WARNING')))
        summary.append('Version ({}) is less than 4.10.x: WARNING'.format(version))
        
else:
    summary.append('Version ({}) is greater than 4.10.x: OK'.format(version))
    flag410 = False


# ## Replication mode check
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
    summary.append('Replication mode is standalone: OK')
    replicationFlag = True
else:
    print(colRed.format('REPLICATION MODE NOT STANDALONE'))
    replicationFlag = False
    summary.append('Replication mode is not standalone: WARNING')
    


# ## Minimum space requirement check
# check if a minimum of MINDISKSPACE GB space is free at /opt/alation/ by calling: df -h /opt/alation
# run bash command
output = subprocess.Popen(["df -BG /opt/alation"],stdout=subprocess.PIPE,shell=True)
# get response
response,val = output.communicate()
# get df readout
installDfOutput = processDfOutput(response)
# get remaining disk space
availSize = float(re.sub("\D", "", installDfOutput['Available']))
# check if there is at least MINDISKSPACE GB space available
if availSize > MINDISKSPACE:
    print('Minimum {}GB disk space (available = {}GB): '.format(MINDISKSPACE,availSize) + colGreen.format('OK'))
    summary.append('Minimum space requirement met: OK')
    diskFlag = True
else:
    print('Minimum 10GB disk space (available = {}GB): '.format(availSize) + colRed.format('FAIL'))
    diskFlag = False
    summary.append('Minimum space requirement not met: FAIL')

# check if disk is at least 90% full
usage = float(re.sub("\D", "", installDfOutput['Use%']))
if usage >= WARNINGATDISKUSE:
    print(colOrange.format('Caution! Disk is {}% full'.format(usage)))


# ## Data drive and backup drive space and mounting check
# data and backup mount check
# run bash command for data drive
output = subprocess.Popen(["df -BG $(cat /opt/alation/alation/.disk1_cache)"],stdout=subprocess.PIPE,shell=True)
# get response
dataResponse,val = output.communicate()
# get df readout
dataDfOutput = processDfOutput(dataResponse)

# run the bash command for backup drive
output = subprocess.Popen(["df -BG $(cat /opt/alation/alation/.disk2_cache)"],stdout=subprocess.PIPE,shell=True)
# get response
backupResponse,val = output.communicate()
# get df readout
backupDfOutput = processDfOutput(backupResponse)

# ensure the mounting points are different for data and backup
if dataDfOutput['Mounted on'] != backupDfOutput['Mounted on']:
    mountFlag = True
    print('Data and backup on different mount: {}'.format(colGreen.format('OK')))
    summary.append('Data and backup on different mounts: OK')
else:
    print('Data and backup on different mount: {}'.format(colRed.format('FAIL')))
    summary.append('Data and backup NOT on different mounts: FAIL')
    mountFlag = False

# ensure the storage devices are different for data and backup
if dataDfOutput['Filesystem'] != backupDfOutput['Filesystem']:
    storageFlag = True
    print('Data and backup on different device: {}'.format(colGreen.format('OK')))
    summary.append('Data and backup on different devices: OK')
else:
    storageFlag = False
    print('Data and backup on different device: {}'.format(colGreen.format('FAIL')))
    summary.append('Data and backup NOT on different devices: FAIL')

# compare backup disk size and data disk size
backupToDataRatio = float(re.sub("\D", "", backupDfOutput['1G-blocks']))/float(re.sub("\D", "", dataDfOutput['1G-blocks']))

# check if backup disk is at least MINBACKUPFACTOR the size of data disk
if backupToDataRatio >= MINBACKUPFACTOR:
    print('Backup disk to data disk size ratio is at least {}: {}'.format(MINBACKUPFACTOR,colGreen.format('OK')))
    summary.append('Backup disk space check passed: OK')
else:
    print('Backup disk to data disk size ratio is {} which is lower than reccommended {}: {}'.format(backupToDataRatio,MINBACKUPFACTOR,colOrange.format('WARNING')))
    summary.append('Backup disk space check not passed: WARNING')


# ## Backup checks
# confirm backups
# get backup drive
with open('/opt/alation/alation/.disk2_cache','r') as f:
    loc = f.readline()

loc = loc.replace('\n','')
    
# read in backup files
backupFilesTemp = listdir(loc+'/backup')
backupFiles = []
for each in backupFilesTemp:
    if "alation_backup.tar.gz" in each:
        backupFiles.append(each)

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
        summary.append('Backup check passed: OK')
        backupFlag = True
    else:
        print('No recent backup available. (Last backup on: {}, age: {}): {}'.format(newestBackup,str(min(tDiff)),colRed.format('FAIL')))
        backupFlag = False
        summary.append('Backup check NOT passed: FAIL')
else:
    print(colRed.format('WARNING! No backup found'))
    summary.append('No backups found: FAIL')
    backupFlag = False


# ## CPU and memory info
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


# ## Mongo Check
# mongoDB check
commands = """cd $(cat /opt/alation/alation/.disk1_cache)
du -k --max-depth=0 -BG ./mongo"""
process = subprocess.Popen('/bin/bash', stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
response, err = process.communicate(commands)

# parase the response
mongoSize = float(re.sub("\D", "", response.split('\t')[0]))
fullLog['mongoSize'] = response.split('\t')[0]

# check if available disk space is at least MONGOx the size of mongoDB
availDataSpace = float(re.sub("\D", "", fullLog['dataDirDf']['Available']))

if availDataSpace/mongoSize > MONGOx:
    print('Available space {}GB is at least {}x greater than mongoDB size {}GB: {}'.format(availDataSpace,MONGOx,mongoSize,colGreen.format('OK')))
    summary.append('MongoDB space check passed: OK')
    mongoFlag = True
else:
    print('{} Not enough space available space to update to Alation V R2 or high! Mongo size = {}, available size = {}.'.format(colRed.format('FAIL'),mongoSize,availDataSpace))
    mongoFlag = False
    summary.append('MongoDB space check not passed: FAIL')


# ## Datadog check
# command to query alation_conf
# this is pure gold
command = '''sudo chroot "/opt/alation/alation" /bin/su - alationadmin -c "alation_conf datadog.enabled"'''
process = subprocess.Popen('/bin/bash', stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
response, err = process.communicate(command)
# parse out the response
key,val = response.replace('\n','').split('=')
key,val = key.strip(),val.strip()
fullLog[key] = val

if val == 'False':
    print("{} Datadog not enabled!".format(colOrange.format('WARNING')))
    datadogFlag = False
elif val == 'True':
    print("Datadog enabled: ".format(colGreen.format('OK')))
    datadogFlag = True

# save log files
with open("/tmp/dataOutput.json", "w") as f:
    json.dump(fullLog,f)
    
summaryStr = '\n'.join(summary)
with open('/tmp/summary.txt','w') as f:
    f.writelines(summaryStr)
    
# create, share, and save a summary
# everything worked
if versionFlag and not flag410 and backupFlag and storageFlag and mountFlag and diskFlag and replicationFlag:
    print(colGreen.format('All critical checks passed'))
    print('Upgrade Readiness Check complete.')
# now enough storage
elif not diskFlag:
    print(colRed.format('Not enough empty space on /opt/alation'))
# backup processing failed
elif not backupFlag:
    print(colRed.format('Do not proceed with upgrade. Please check backup.'))
# not enough mongo space
elif not mongoFlag:
    print(colOrange.format('Not enough space for mongoDB.'))
elif not replicationFlag:
    print(colOrange.format('Please follow the High-Availability install instructions here: https://alationhelp.zendesk.com/hc/en-us/articles/360011041633-Release-Specific-Update-Pre-Checks '))
elif flag410:
    print(colOrange.format('Alation version is lower than 4.10.x. Please see https://alationhelp.zendesk.com/hc/en-us/articles/360011041633-Release-Specific-Update-Pre-Checks '))
elif not mountFlag or not storageFlag:
    print(colOrange.format('Backup and data drives share same device'))
elif not versionFlag:
    print(colRed.format('Please contact customer care. Version not supported'))