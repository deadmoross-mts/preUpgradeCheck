# ## Libraries and functions
# import libraries
import subprocess
import re
from os import listdir
import csv
import datetime
import time
import json

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
    response = response.replace('Mounted on','Mounted_on').replace('\n',' ')
    # remove extra spaces
    temp = re.sub(' +',' ',response).split(' ')
    # split the lists
    labs = temp[0:6]
    vals = temp[6:]

    # create a dictionary
    dfOutput = dict(zip(labs,vals))
    
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
    
def colPrint(inStr,color):
    # create output templates
    if color == 'G':
        # all clear = green
        colPrintOut = '\x1b[6;30;42m' + inStr + '\x1b[0m'
    elif color == 'R':
        # warning = red
        colPrintOut = '\x1b[6;30;41m' + inStr + '\x1b[0m'
    elif color == 'O':
        # caution = orange
        colPrintOut = '\x1b[6;30;43m' + inStr + '\x1b[0m'
        
    return(colPrintOut)

# ## Version information check
def versionCheck(summary):
    # run the version check
    # run bash command and get the response
    cmd = """sudo chroot "/opt/alation/alation" /bin/su - alation
    cat /opt/alation/django/main/alation_version.py"""
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
        print('Version > {} (current version = {}): '.format(CRITICALVERSION,version) + colPrint('OK!','G'))
        summary.append('Version ({}) check passed: OK'.format(version))
        versionFlag = True
    else:
        print('Version > {} (current version = {}): '.format(CRITICALVERSION,version) + colPrint('FAIL!','R'))
        versionFlag = False
        summary.append('Version ({}) check failed: FAIL'.format(version))

    # check additional version information
    if majorVersion <= 4:
        if minorVersion <= 10:
            flag410 = True
            print('{} Be sure to follow 4.10.x or below version specific steps here: https://alationhelp.zendesk.com/hc/en-us/articles/360011041633-Release-Specific-Update-Pre-Checks'.format(colPrint('WARNING!','O')))
            summary.append('Version ({}) is less than 4.10.x: WARNING'.format(version))
        
    else:
        summary.append('Version ({}) is greater than 4.10.x: OK'.format(version))
        flag410 = False
        
    return(versionData,majorVersion,minorVersion,patchVersion,buildVersion,version,versionFlag,flag410,summary)

# ## Replication mode check
def replicationCheck(summary):
    # check replication
    # define commands
    cmd = "curl -L --insecure http://localhost/monitor/replication/"
    # get response
    response = bashCMD(cmd)
    # process response
    replicationMode = response.split('{')[1].split('}')[0].split(': ')[1].replace('"','')

    # check replication criteria
    if replicationMode == 'standalone':
        print('Replication mode standalone: ' + colPrint('OK!','G'))
        summary.append('Replication mode is standalone: OK')
        replicationFlag = True
    else:
        print(colPrint('REPLICATION MODE NOT STANDALONE!','R'))
        replicationFlag = False
        summary.append('Replication mode is not standalone: WARNING')
    
    return(summary,replicationMode,replicationFlag)
    
# ## Minimum space requirement check
def minSpaceCheck(summary):
    # check if a minimum of MINDISKSPACE GB space is free at /opt/alation/ by calling: df -h /opt/alation
    # define command
    cmd = """sudo chroot "/opt/alation/alation" /bin/su - alation
    df -BG /"""
    # run bash command and get response
    response = bashCMD(cmd)
    # get df readout
    installDfOutput = processDfOutput(response)
    # get remaining disk space
    availSize = float(re.sub("\D", "", installDfOutput['Available']))
    # check if there is at least MINDISKSPACE GB space available
    if availSize > MINDISKSPACE:
        print('Minimum {}GB disk space (available in /opt/alation = {}GB): '.format(MINDISKSPACE,availSize) + colPrint('OK!','G'))
        summary.append('Minimum space requirement met: OK')
        diskFlag = True
    else:
        print('Minimum {}GB disk space (available in /opt/alation = {}GB): '.format(MINDISKSPACE,availSize) + colPrint('FAIL!','R'))
        diskFlag = False
        summary.append('Minimum space requirement not met: FAIL')

    # check if disk is at least 90% full
    usage = float(re.sub("\D", "", installDfOutput['Use%']))
    if usage >= WARNINGATDISKUSE:
        print(colPrint('Caution! /opt/alation is {}% full'.format(usage),'O'))
        
    return(installDfOutput,availSize,summary,usage,diskFlag)
    
# ## Data drive and backup drive space and mounting check
def dataAndBackupDriveCheck(summary):
    # data and backup mount check
    # define bash command for data drive
    cmd = """sudo chroot "/opt/alation/alation" /bin/su - alation
    df -BG /data1/"""
    # run bash command and get response
    dataResponse = bashCMD(cmd)
    # get df readout
    dataDfOutput = processDfOutput(dataResponse)

    # define bash command for backup drive
    cmd = """sudo chroot "/opt/alation/alation" /bin/su - alation
    df -BG /data2/"""
    # run bash command and get response
    backupResponse = bashCMD(cmd)
    # get df readout
    backupDfOutput = processDfOutput(backupResponse)

    # ensure the mounting points are different for data and backup
    if dataDfOutput['Mounted_on'] != backupDfOutput['Mounted_on']:
        mountFlag = True
        print('Data and backup on different mount: {}'.format(colPrint('OK!','G')))
        summary.append('Data and backup on different mounts: OK')
    else:
        print('Data and backup on different mount: {}'.format(colPrint('FAIL!','R')))
        summary.append('Data and backup NOT on different mounts: FAIL')
        mountFlag = False

    # ensure the storage devices are different for data and backup
    if dataDfOutput['Filesystem'] != backupDfOutput['Filesystem']:
        storageFlag = True
        print('Data and backup on different device: {}'.format(colPrint('OK!','G')))
        summary.append('Data and backup on different devices: OK')
    else:
        storageFlag = False
        print('Data and backup on different device: {}'.format(colPrint('FAIL!','R')))
        summary.append('Data and backup NOT on different devices: FAIL')

    # compare backup disk size and data disk size
    backupToDataRatio = float(re.sub("\D", "", backupDfOutput['1G-blocks']))/float(re.sub("\D", "", dataDfOutput['1G-blocks']))

    # check if backup disk is at least MINBACKUPFACTOR the size of data disk
    if backupToDataRatio >= MINBACKUPFACTOR:
        print('Backup disk to data disk size ratio is at least {}: {}'.format(MINBACKUPFACTOR,colPrint('OK!','G')))
        summary.append('Backup disk space check passed: OK')
    else:
        print('Backup disk to data disk size ratio is {} which is lower than reccommended {}: {}'.format(backupToDataRatio,MINBACKUPFACTOR,colPrint('WARNING','O')))
        summary.append('Backup disk space check not passed: WARNING')
    
    return(summary,backupToDataRatio,backupDfOutput,storageFlag,mountFlag,dataDfOutput)

# ## Backup checks
def confirmBackups(summary):
    # confirm backups
    # read in backup files
    cmd = """sudo chroot "/opt/alation/alation" /bin/su - alation
    ls -l --block-size=M /data2/backup/"""
    # run bash command and get response
    response = bashCMD(cmd)

    backupFilesTemp = response.split('\n')
    backupFiles = []
    fileDatMap = {}
    for each in backupFilesTemp:
        if "alation_backup.tar.gz" in each:
            # get date
            dtTemp = each.split(' ')[-1]
            # get filename
            backupFiles.append(dtTemp)
            # map filename to data
            fileDatMap[dtTemp.split('_')[0][:8]] = each
        

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
    response = fileDatMap[newestBackup]
    # process the response (fize size in MB)
    fileSize = float(response.split(' ')[4].replace('M',''))

    # check if the backup filesize is at least 10 MB
    if fileSize <= 10:
        print(colPrint('Backup file size {} less than 10 MB'.format(fileSize),'R'))

    # get the newest backup
    newestBackup = diffRes[min(tDiff)].strftime('%Y-%m-%d')
    # check age of the backup
    if len(backupDates) >= 1:
        if min(tDiff) <= MAXBACKUPAGE:
            print('Recent backup available (Last backup on: {}, filesize: {}MB): {}'.format(newestBackup,fileSize,colPrint('OK!','G')))
            summary.append('Backup check passed: OK')
            backupFlag = True
        else:
            print('No recent backup available. (Last backup on: {}, age: {}): {}'.format(newestBackup,str(min(tDiff)),colPrint('FAIL!','R')))
            backupFlag = False
            summary.append('Backup check NOT passed: FAIL')
    else:
        print(colPrint('WARNING! No backup found!','R'))
        summary.append('No backups found: FAIL')
        backupFlag = False
        
    return(summary,backupFlag,backupFiles)

# ## CPU and memory info
def cpuMemData(summary):
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
    
    return(summary,memResponse,lscpuOutput)

# ## Mongo Check
def mongoCheck(summary,fullLog):
    # mongoDB check
    cmd = """sudo chroot "/opt/alation/alation" /bin/su - alation
    du -k --max-depth=0 -BG /data1/mongo/"""
    # get response
    response = bashCMD(cmd)

    # parase the response
    mongoSize = float(re.sub("\D", "", response.split('\t')[0]))
    fullLog['mongoSize'] = response.split('\t')[0]

    # check if available disk space is at least MONGOx the size of mongoDB
    availDataSpace = float(re.sub("\D", "", fullLog['dataDirDf']['Available']))
    print('Space available in data drive: {}GB'.format(availDataSpace))

    if availDataSpace/mongoSize > MONGOx:
        print('Available space {}GB in /data1/ is at least {}x greater than mongoDB size {}GB: {}'.format(availDataSpace,MONGOx,mongoSize,colPrint('OK!','G')))
        summary.append('MongoDB space check passed: OK')
        mongoFlag = True
    else:
        print('{} Not enough space available space in /data1/ to update to Alation V R2 or higher! Mongo size = {}GB, available size = {}GB.'.format(colPrint('FAIL!','R'),mongoSize,availDataSpace))
        mongoFlag = False
        summary.append('MongoDB space check not passed: FAIL')
    
    return(summary,mongoFlag,fullLog,availDataSpace,mongoSize)
    
# ## postgreSQL Check
def pgSQLCheck(summary,fullLog):
    # postgreSQL check
    cmd = """sudo chroot "/opt/alation/alation" /bin/su - alation
    du -k --max-depth=0 -BG /data1/pgsql/"""
    # get response
    response = bashCMD(cmd)

    # parase the response
    pgsqlSize = float(re.sub("\D", "", response.split('\t')[0]))
    fullLog['pgsqlSize'] = response.split('\t')[0]

    # run the check
    if availDataSpace/pgsqlSize > PGSQLx:
        print('(For Alation Analytics) Available space in /data1/ {}GB is at least {}x greater than postgreSQL size {}GB: {}'.format(availDataSpace,PGSQLx,pgsqlSize,colPrint('OK!','G')))
        summary.append('postgreSQL for Analytics space check passed: OK')
        pgsqlFlag = True
    else:
        print('{} Not enough space available space in /data1/ to turn on analytics. postgreSQL size = {}, available size = {}.'.format(colPrint('WARNING','O'),pgsqlSize,availDataSpace))
        pgsqlFlag = False
        summary.append('postgreSQL for Analytics space check not passed: FAIL')

    # ## combined space check
    fullSpaceNeeded = pgsqlSize*PGSQLx + mongoSize*MONGOx

    # check against available space
    if availDataSpace > fullSpaceNeeded:
        print('Available space, {}GB, is greater than the combined space needed, {}GB: {}'.format(availDataSpace,fullSpaceNeeded,colPrint('OK!','G')))
        combinedSpaceFlag = True
    else:
        spaceDiff = abs(fullSpaceNeeded - availDataSpace)
        print('{} Combined space check Please expand /opt/alation/ drive by {}GB before turning on analytics!'.format(colPrint('WARNING!','O'),spaceDiff))
        combinedSpaceFlag = False
        
    return(combinedSpaceFlag,pgsqlFlag,summary,fullLog)

# ## datadog check
def dataDogCheck(fullLog):
    # Datadog check
    key,val = alationConfQuery('datadog.enabled')
    fullLog[key] = val

    if val == 'False':
        print("{} Datadog not enabled!".format(colPrint('WARNING','O')))
        datadogFlag = False
    elif val == 'True':
        print("Datadog enabled: ".format(colPrint('OK!','G')))
        datadogFlag = True
        
    return(fullLog,datadogFlag)
    
## # Extract site ID
def siteIDExtract(fullLog):
    # site_id
    key,siteID = alationConfQuery('site_id')
    fullLog[key] = siteID
    
    return(fullLog,siteID)
    
# parse out the information 
def fileParser(inMessage):
    if len(inMessage) > 1 and ':' in inMessage:
        # split out the directory name and response
        k,v = inMessage.split(':')
        k = k.strip()
        v = v.strip()
        # return values
        return(k,v)
    else:
        return(False,False)

def slLogic(dirToCheck,slFullRes):
    # check information for dirToCheck
    res = slFullRes.get(dirToCheck,False)
    # check if result came back
    if res:
        # check if the result is the expected result
        if res == "directory":
            print('{} is not a symbolic link: {}'.format(dirToCheck,colPrint('OK!','G')))
            return(True)
        else:
            print('{} is a symbolic link: {}'.format(dirToCheck,colPrint('FAIL!','R')))
            return(False)
    # if the result did not come back
    else:
        print('Cannot verify if {} is a symbolic link: {}'.format(dirToCheck,colPrint('FAIL!','R')))
        return(False)

# ## Symbolic Link Check
def slCheck():
    # output dict
    slFullRes = {}
    # create bash command
    cmd = "file /opt && file /opt/alation"
    # get response
    slResponse = bashCMD(cmd)
    # parse out all the responses
    resList = slResponse.split('\n')
    # split out each message
    for res in resList:
        # get the inputs
        k,v = fileParser(res)
        if k and v:
            # add to result dataset
            slFullRes[k] = v
    
    # check information for /opt
    optFlag = slLogic('/opt',slFullRes)
    # check information for /opt/alation
    optAlationFlag = slLogic('/opt/alation',slFullRes)
    
    return(optFlag,optAlationFlag)

# ## get version information
def linuxVersionInfo():
    # create the command
    cmd = 'cat /proc/version'
    # run and get response
    vResponse = bashCMD(cmd).strip()
    return(vResponse)
    
# ## Get previously installed Alation versions
def alationVerHist():
    # create the command
    cmd = 'update-alternatives --display alation'
    # run and get response
    avResponse = bashCMD(cmd).strip().replace('\n','|')
    return(avResponse)

# ## Configuration parameters
# config
# minimum empty disk requirement
MINDISKSPACE = 15.0
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
# postgreSQL multiplication factor for analytics
# in order to turn on analytics, the pgsql folder will doulbe 
# in size.
PGSQLx = 2
# flag to indicate code failure
failure = False
# steps to be run manually
steps = []

# summary object for the end
summary = []

##################
# Code start
##################

# ## Version information check
try:
    versionData,majorVersion,minorVersion,patchVersion,buildVersion,version,versionFlag,flag410,summary = versionCheck(summary)
except:
    versionFlag = False
    flag410 = False
    failure = True
    steps.append('2')
    print(colPrint('WARNING! Version check failed! Please make sure Alation version is > 4.10.x','R'))


# ## Replication mode check
try:
    summary,replicationMode,replicationFlag = replicationCheck(summary)
except:
    replicationFlag = False
    failure = True
    steps.append('3')
    print(colPrint('WARNING! Replication check failed! Please make sure the installation is standalone!','R'))


# ## Minimum space requirement check
try:
    installDfOutput,availSize,summary,usage,diskFlag = minSpaceCheck(summary)
except:
    diskFlag = False
    failure = True
    steps.append('4')
    print(colPrint('WARNING! Minimum space check failed! Please make sure /opt/alation has 8GB free space.','R'))


# ## Data drive and backup drive space and mounting check
try:
    summary,backupToDataRatio,backupDfOutput,storageFlag,mountFlag,dataDfOutput = dataAndBackupDriveCheck(summary)
except:
    storageFlag,mountFlag = False,False
    failure = True
    steps.append('5')
    print(colPrint('WARNING! Could not verify separation of data and backup disk!','R'))


# ## Backup checks
try:
    summary,backupFlag,backupFiles = confirmBackups(summary)
except:
    backupFlag = False
    failure = True
    steps.append('6')
    print(colPrint('WARNING! Could not verify backups!','R'))


# ## CPU and memory info
try:
    summary,memResponse,lscpuOutput = cpuMemData(summary)
except:
    print(colPrint('Could not obtain CPU and memory Information','O'))
    
# ## get linux version information
try:
    vResponse = linuxVersionInfo()
except:
    print(colPrint('Could not obtain Linux version information','O'))

# ## get Alation version history
try:
    avResponse = alationVerHist()
except:
    print(colPrint('Could not obtain Alation version history','O'))

try:
    # parse out version data collected before
    vDataTemp = list(map(lambda x: versionParser(x),versionData))
    keys = list(map(lambda x: x[0],vDataTemp))
    values = list(map(lambda x: x[1],vDataTemp))
    fullLog = dict(zip(keys,values))

    # add previously obtained data
    try:
        fullLog['backupFiles'] = backupFiles
    except:
        pass
    try:
        fullLog['Replication'] = replicationMode
    except:
        pass
    try:
        fullLog['installDirDf'] = installDfOutput
    except:
        pass
    try:
        fullLog['dataDirDf'] = dataDfOutput
    except:
        pass
    try:
        fullLog['backupDirDf'] = backupDfOutput
    except:
        pass
    try:
        fullLog['backupToDataRatio'] = backupToDataRatio
    except:
        pass
    try:
        fullLog['cpuData'] = lscpuOutput
    except:
        pass
    try:
        fullLog['totalMemory'] = memResponse.values()[0]
    except:
        pass
    try:
        fullLog['linuxVersion'] = vResponse
    except:
        pass
    try:
        fullLog['alationVerHist'] = avResponse
    except:
        pass
except:
    fullLog={}

# ## Mongo Check
try:
    summary,mongoFlag,fullLog,availDataSpace,mongoSize = mongoCheck(summary,fullLog)
except:
    mongoFlag = False
    failure = True
    steps.append('8')
    print(colPrint('WARNING! Could not check disk space for MongoDB!','R'))

# ## postgreSQL Check
try:
    combinedSpaceFlag,pgsqlFlag,summary,fullLog = pgSQLCheck(summary,fullLog)
except:
    combinedSpaceFlag,pgsqlFlag = False,False
    failure = True
    steps.append('10')
    print(colPrint('Caution! Could not verify the space requirements for Alation Analytics!','O'))

# ## Query alation_conf for Datadog check and site_id
try:
    fullLog,datadogFlag = dataDogCheck(fullLog)
except:
    datadogFlag = False
    print(colPrint('Datadog status could not be verified!','O'))

## # Extract site ID
try:
    fullLog,siteID = siteIDExtract(fullLog)
except:
    siteID = 'NA'

# ## Symbolic Link Check
# we need to check if /opt and /opt/alation/ is a symbolic link or not
try:
    optFlag,optAlationFlag = slCheck()
except:
    print('Could not if verify /opt and /opt/alation/ are symbolic link(s) or not! {}'.format(colPrint('WARNING!','O')))
    optFlag,optAlationFlag = False,False

# add current time
ts = time.time()
fullLog['creationTime'] = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')    

# print our the full log
print('##########')
print(fullLog)
print('##########')

# create, share, and save a summary
# everything worked
if versionFlag and not flag410 and backupFlag and storageFlag and mountFlag and diskFlag and replicationFlag and mongoFlag and optFlag and optAlationFlag:
    print(colPrint('All critical checks passed.\nPlease copy and send all the output back to Alation!','G'))
    print('Upgrade Readiness Check complete.')
# now enough storage
elif not diskFlag:
    print(colPrint('Not enough empty space on /opt/alation!','R'))
# backup processing failed
elif not backupFlag:
    print(colPrint('Do not proceed with upgrade. Please check backup!','R'))
# not enough mongo space
elif not mongoFlag:
    print(colPrint('Not enough space for mongoDB or the code could not read the disk size!','R'))
elif not replicationFlag:
    print(colPrint('Please follow the High-Availability install instructions here: https://alationhelp.zendesk.com/hc/en-us/articles/115006108927-Upgrade-on-an-HA-Pair-Configuration-4-7-and-above-','O'))
elif flag410:
    print(colPrint('Alation version is lower than 4.10.x. Please see https://alationhelp.zendesk.com/hc/en-us/articles/360011041633-Release-Specific-Update-Pre-Checks','O'))
elif not mountFlag or not storageFlag:
    print(colPrint('Backup and data drives share same device!','O'))
elif not versionFlag:
    print(colPrint('Please contact customer care. Version not supported!','R'))

if failure:
    print(colPrint('Python failed to verify some information.\nPlease follow manual instruction step 1 + step(s) {} in the readiness guide.'.format(','.join(steps)),'O'))

try:
    # write data to disk
    # data filename
    dfName = "/tmp/dataOutput_{}.json".format(siteID)
    # write to disk
    with open(dfName, "w") as f:
        json.dump(fullLog,f)

    # process the summary
    summaryStr = '\n'.join(summary)
    # summary filename
    sfName = "/tmp/summary_{}.txt".format(siteID)
    # write to disk
    with open(sfName,'w') as f:
        f.writelines(summaryStr)
except:
    pass