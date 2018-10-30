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

# create a function to execute bash commands
def bashCMD(command):
    # open a process
    process = subprocess.Popen('/bin/bash', stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # execute command and capture result
    response, err = process.communicate(command)
    # return response
    return(response)

# a function defined to run alation shell "alation_conf" command
def alationConfQuery(configVal):
    # define command
    cmd = '''sudo chroot "/opt/alation/alation" /bin/su - alationadmin -c "alation_conf {}"'''.format(configVal)
    response = bashCMD(cmd)
    # parse out the response
    key,val = response.replace('\n','').split('=')
    key,val = key.strip(),val.strip()
    # return response
    return(key,val)

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
# run bash command and get the response
cmd = "cat /opt/alation/alation/opt/alation/django/main/alation_version.py"
response = bashCMD(cmd)
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
cmd = "curl -L --insecure http://localhost/monitor/replication/"
# get response
response = bashCMD(cmd)
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
# define command
cmd = "df -BG /opt/alation"
# run bash command and get response
response = bashCMD(cmd)
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
# define bash command for data drive
cmd = "df -BG $(cat /opt/alation/alation/.disk1_cache)"
# run bash command and get response
dataResponse = bashCMD(cmd)
# get df readout
dataDfOutput = processDfOutput(dataResponse)

# define bash command for backup drive
cmd = "df -BG $(cat /opt/alation/alation/.disk2_cache)"
# run bash command and get response
backupResponse = bashCMD(cmd)
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

# get the newest backup file
newestBackup = diffRes[min(tDiff)].strftime('%Y%m%d')
# get backup filesize information
cmd = """ls -l --block-size=M {}""".format(loc+'/backup/*{}*'.format(newestBackup))
# run bash command and get response
response = bashCMD(cmd)
# process the response (fize size in MB)
fileSize = float(response.split(' ')[4].replace('M',''))

# check if the backup filesize is at least 10 MB
if fileSize <= 10:
    print(colRed.format('Backup file size {} less than 10 MB'.format(fileSize)))

# get the newest backup
newestBackup = diffRes[min(tDiff)].strftime('%Y-%m-%d')
# check age of the backup
if len(backupDates) >= 1:
    if min(tDiff) <= MAXBACKUPAGE:
        print('Recent backup available (Last backup on: {}, filesize: {}MB): {}'.format(newestBackup,fileSize,colGreen.format('OK')))
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
# define commands
cmd = "lscpu"
# get response
cpuResponse = bashCMD(cmd)
# process response
lscpuOutput = lscpuParser(cpuResponse)

# get total memory information
# define commands
cmd = "grep MemTotal /proc/meminfo"
# get response
memResponse = bashCMD(cmd)
# process response
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
cmd = """cd $(cat /opt/alation/alation/.disk1_cache)
du -k --max-depth=0 -BG ./mongo"""
# get response
response = bashCMD(cmd)

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


# ## Query alation_conf for Datadog check, client_id, and site_id
# Datadog check
key,val = alationConfQuery('datadog.enabled')
fullLog[key] = val

if val == 'False':
    print("{} Datadog not enabled!".format(colOrange.format('WARNING')))
    datadogFlag = False
elif val == 'True':
    print("Datadog enabled: ".format(colGreen.format('OK')))
    datadogFlag = True
    
# client_id
key,clientID = alationConfQuery('client_id')
fullLog[key] = clientID
# site_id
key,siteID = alationConfQuery('site_id')
fullLog[key] = clientID


# write data to disk
# data filename
dfName = "/tmp/dataOutput_{}_{}.json".format(clientID,siteID)
# write to disk
with open(dfName, "w") as f:
    json.dump(fullLog,f)

# process the summary
summaryStr = '\n'.join(summary)
# summary filename
sfName = "/tmp/summary_{}_{}.txt".format(clientID,siteID)
# write to disk
with open(sfName,'w') as f:
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