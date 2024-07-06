import os
import sys
import shutil
import datetime
import zipfile
import tkinter as tk
import requests
import json
import subprocess
import threading

#TO DO:
#Get the current version when manually updating
#{name} in instance naming is currently actually equal to ID, it should be name (maybe stay as ID for the new ID?)
#Auto determine java version
#Auto script update
#Check version online before updating local, to avoid updating from local when theres a newer version online (make sure to still prioritize local downloads vs online for same version)
#Main instance renaming in background after post command
#First time setup
#Better way to determine version
#Smart config combining
#Regex for mods and configs
#Directories for mods and configs

CONFIG_FILE_PATH = "AutoNH/AutoNH.cfg"

def sanitizeUserPath(path, default = None):
    if (not path) or (path.strip() == ""):
        if not default:
            return default
        else:
            path = default
    stripped = path.strip()
    replaced = stripped.replace("\\", "/")
    split = replaced.split("/")
    return os.path.join(*split)

def readConfig():
    def sanitizeUserStr(str, default = None):
        if str:
            return str
        else:
            return default

    def sanitizeUserBool(str, default = None):
        trues = ["true", "t", "yes", "y"]
        falses = ["false", "f", "no", "n"]

        if not str:
            return default

        folded = str.casefold()
        if folded in trues:
            return True
        elif folded in falses:
            return False
        else:
            return default
        
    def sanitizeUserInt(str, default = None):
        if str and str.isdecimal():
            return int(str)
        else:
            return default

    configPath = sanitizeUserPath(CONFIG_FILE_PATH, "AutoNH/AutoNH.cfg")
    values = {}
    with open(configPath, "r") as file:
        for line in file.readlines():
            stripped = line.strip()
            if stripped == "" or stripped[0] == "#":
                continue

            split = stripped.split("=")
            key = split[0].strip()
            if len(split) > 1:
                values[key] = "=".join(split[1:]).strip()
            else:
                values[key] = None

    # Set globals to the values read from the config file, or a default if there's a issue
    # This could be made significantly shorter using a list, exec(), and some fancy string formatting, but it would be basically unreadable
    global BACKUP_INSTANCE_NEW_NAME
    if "backupInstanceNewName" in values:
        BACKUP_INSTANCE_NEW_NAME = sanitizeUserStr(values["backupInstanceNewName"], "%Y-%m-%d_%H%M%S GTNH {oldVersion} Backup")
    else:
        BACKUP_INSTANCE_NEW_NAME = "%Y-%m-%d_%H%M%S GTNH {oldVersion} Backup"

    global ENABLE_DATETIME_FORMATTING
    if "enableDatetimeFormatting" in values:
        ENABLE_DATETIME_FORMATTING = sanitizeUserBool(values["enableDatetimeFormatting"], True)
    else:
        ENABLE_DATETIME_FORMATTING = True

    global PRISM_INSTANCE_BACKUPS_GROUP
    if "backupPrismGroup" in values:
        PRISM_INSTANCE_BACKUPS_GROUP = sanitizeUserStr(values["backupPrismGroup"], None)
    else:
        PRISM_INSTANCE_BACKUPS_GROUP = None

    global CHECK_ONLINE_AFTER_LOCAL_UPDATE
    if "checkOnlineAfterLocalUpdate" in values:
        CHECK_ONLINE_AFTER_LOCAL_UPDATE = sanitizeUserBool(values["checkOnlineAfterLocalUpdate"], True)
    else:
        CHECK_ONLINE_AFTER_LOCAL_UPDATE = True

    global COPY_RESOURCE_PACKS_FROM_DOWNLOAD
    if "copyResourcePacksFromDownload" in values:
        COPY_RESOURCE_PACKS_FROM_DOWNLOAD = sanitizeUserBool(values["copyResourcePacksFromDownload"], True)
    else:
        COPY_RESOURCE_PACKS_FROM_DOWNLOAD = True

    global DELETE_ZIP_AFTER_DOWNLOAD
    if "deleteZipAfterDownload" in values:
        DELETE_ZIP_AFTER_DOWNLOAD = sanitizeUserBool(values["deleteZipAfterDownload"], True)
    else:
        DELETE_ZIP_AFTER_DOWNLOAD = True

    global DELETE_FILES_AFTER_UPDATE
    if "deleteFilesAfterUpdate" in values:
        DELETE_FILES_AFTER_UPDATE = sanitizeUserBool(values["deleteFilesAfterUpdate"], False)
    else:
        DELETE_FILES_AFTER_UPDATE = False

    global JAVA_17_21
    if "Java1721" in values:
        JAVA_17_21 = sanitizeUserBool(values["Java1721"], True)
    else:
        JAVA_17_21 = True

    global DOWNLOAD_DIRECTORY
    if "downloadDirectory" in values:
        DOWNLOAD_DIRECTORY = sanitizeUserPath(values["downloadDirectory"], "AutoNH/downloads")
    else:
        DOWNLOAD_DIRECTORY = sanitizeUserPath("AutoNH/downloads")

    global VERSION_TRACKER_PATH
    if "versionTrackerPath" in values:
        VERSION_TRACKER_PATH = sanitizeUserPath(values["versionTrackerPath"], "AutoNH/versions.txt")
    else:
        VERSION_TRACKER_PATH = sanitizeUserPath("AutoNH/versions.txt")

    global CONFIG_OVERWRITE_PATH
    if "configOverwritePath" in values:
        CONFIG_OVERWRITE_PATH = sanitizeUserPath(values["configOverwritePath"], "AutoNH/configs.txt")
    else:
        CONFIG_OVERWRITE_PATH = sanitizeUserPath("AutoNH/configs.txt")

    global MOD_OVERWRITE_PATH
    if "modOverwritePath" in values:
        MOD_OVERWRITE_PATH = sanitizeUserPath(values["modOverwritePath"], "AutoNH/mods.txt")
    else:
        MOD_OVERWRITE_PATH = sanitizeUserPath("AutoNH/mods.txt")

    global AUTONH_PATH
    if "AutoNHPath" in values:
        AUTONH_PATH = sanitizeUserPath(values["AutoNHPath"], "AutoNH/AutoNH.py")
    else:
        AUTONH_PATH = sanitizeUserPath("AutoNH/AutoNH.py")

    global PYTHON_EXECUTABLE
    if "pythonExecutable" in values:
        PYTHON_EXECUTABLE = sanitizeUserPath(values["pythonExecutable"], "python")
    else:
        PYTHON_EXECUTABLE = "python"

    global DOWNLOAD_LIST_URL
    if "downloadListURL" in values:
        DOWNLOAD_LIST_URL = sanitizeUserStr(values["downloadListURL"], "https://downloads.gtnewhorizons.com/Multi_mc_downloads/?raw")
    else:
        DOWNLOAD_LIST_URL = "https://downloads.gtnewhorizons.com/Multi_mc_downloads/?raw"

    global DOWNLOAD_CHUNK_SIZE
    if "downloadChunkSize" in values:
        DOWNLOAD_CHUNK_SIZE = sanitizeUserInt(values["downloadChunkSize"], 16384)
    else:
        DOWNLOAD_CHUNK_SIZE = 16384

def getInstanceVersion(instanceID):
    if not os.path.exists(VERSION_TRACKER_PATH):
        return [0,0,0]

    with open(VERSION_TRACKER_PATH, "r") as file:
        lines = file.readlines()

    for line in lines:
        split = line.split(",")
        ID = ",".join(split[:-1])
        if ID == instanceID:
            return [ int(i) for i in split[-1].strip().split(".") ]

    return [0,0,0]

def getVersionNumberFromFileName(filename, splitChar = "_"):
    return [int(i) for i in filename.split(splitChar)[3].split(".")]

def promptUser(labelText, buttonTexts):
    def buttonFunc(retVal):
        global UIRetValue
        UIRetValue = retVal
        root.destroy()
        
    global UIRetValue
    UIRetValue = -1

    root = tk.Tk()
    root.title("AutoNH")
    tk.Label(root, text = labelText).pack()
    for i in range(len(buttonTexts)):
        buttonText = buttonTexts[i]
        tk.Button(root, text = buttonText, command = lambda retVal=i: buttonFunc(retVal)).pack()

    root.mainloop()
    
    return UIRetValue

def createInstanceBackup(instanceDir, oldVersion, newVersion):
    if not os.path.exists(instanceDir):
        return None
    
    if ENABLE_DATETIME_FORMATTING:
        newNameBase = datetime.datetime.now().strftime(BACKUP_INSTANCE_NEW_NAME)
    else:
        newNameBase = BACKUP_INSTANCE_NEW_NAME

    head, currID = os.path.split(os.path.normpath(instanceDir))
    newID = newNameBase.format(name=currID, oldVersion = ".".join([str(i) for i in oldVersion]), newVersion = ".".join([str(i) for i in newVersion]))

    #Copy instance files
    dstDir = os.path.join(head, newID)
    shutil.copytree(instanceDir, dstDir)

    #Rename new instance and remove startup and exit commands
    newInstanceConfigFilename = os.path.join(dstDir, "instance.cfg")
    with open(newInstanceConfigFilename, "r+") as file:
        lines = file.readlines()
        file.seek(0)
        for line in lines:
            key = line.split("=")[0]
            if key == "name":
                currName = "=".join(line.split("=")[1:]).strip()
                newName = newNameBase.format(name=currName, oldVersion = ".".join([str(i) for i in oldVersion]), newVersion = ".".join([str(i) for i in newVersion]))
                file.write("name=" + newName + "\n")
            elif key == "PreLaunchCommand" or key == "PostExitCommand":
                pass
            else:
                file.write(line)
        
        file.truncate()

    if PRISM_INSTANCE_BACKUPS_GROUP:
        #Add new instance to PRISM_INSTANCE_BACKUPS_GROUP group in Prism (and create the group if it doesn't already exist)
        prismGroupsFilename = os.path.join(os.path.dirname(dstDir), "instgroups.json")
        if os.path.exists(prismGroupsFilename):
            with open(prismGroupsFilename, "r+") as file:
                obj = json.loads(file.read())
        
                if PRISM_INSTANCE_BACKUPS_GROUP in obj["groups"]:
                    obj["groups"][PRISM_INSTANCE_BACKUPS_GROUP]["instances"].append(os.path.basename(dstDir))
                else:
                    obj["groups"][PRISM_INSTANCE_BACKUPS_GROUP] = {"hidden": True, "instances": [os.path.basename(dstDir)]}

                file.seek(0)
                file.write(json.dumps(obj, indent = 4))
                file.truncate()
        else:
            with open(prismGroupsFilename, "w") as file:
                obj = json.loads("{\"formatVersion\": \"1\",\"groups\": {}}")
                obj["groups"][PRISM_INSTANCE_BACKUPS_GROUP] = {"hidden": True, "instances": [os.path.basename(dstDir)]}
                file.write(json.dumps(obj, indent = 4))

    return dstDir

def updateInstanceVersion(instanceID, versionNumber):
    versionNumStr = ".".join([str(i) for i in versionNumber])

    if not os.path.exists(VERSION_TRACKER_PATH):
        with open(VERSION_TRACKER_PATH, "w") as file:
            file.write(instanceID + "," + versionNumStr + "\n")
    else:
        with open(VERSION_TRACKER_PATH, "r+") as file:
            start = file.tell()
            line = file.readline()
            while line:
                split = line.split(",")
                ID = ",".join(split[:-1])
                if ID == instanceID:
                    break
                start = file.tell()
                line = file.readline()
    
            restOfFile = file.read()
            file.seek(start)
            file.write(instanceID + "," + versionNumStr + "\n" + restOfFile)
            file.truncate()
            
def updateInstance(instanceDirIn, downloadDirIn, oldVersion, backupDir = None):
    if not (os.path.exists(instanceDirIn) and os.path.exists(downloadDirIn)):
        return False
    
    instanceDir = os.path.normpath(instanceDirIn)
    instanceID = os.path.basename(instanceDir)

    if os.path.isfile(downloadDirIn) and os.path.splitext(downloadDirIn)[1] == (".zip"):
        downloadDir = extractZip(downloadDirIn)
        if downloadDir == None:
            return False
    elif os.path.isdir(downloadDirIn):
        downloadDir = os.path.normpath(downloadDirIn)
    else:
        return False

    newVersion = getVersionNumberFromFileName(downloadDir, " ")

    if not backupDir:
        backupDir = createInstanceBackup(instanceDir, oldVersion, newVersion)
        if not backupDir:
            return False

    #Rename instance
    #Doesn't work :(
    #with open(os.path.join(instanceDir, "instance.cfg"), "r+") as file:
    #    lines = file.readlines()
    #    file.seek(0)
    #    for line in lines:
    #        key = line.split("=")[0]
    #        if key == "name":
    #            currName = "=".join(line.split("=")[1:]).strip()
    #            newName = MAIN_INSTANCE_NEW_NAME.format(name=currName, oldVersion = ".".join([str(i) for i in oldVersion]), newVersion = ".".join([str(i) for i in newVersion]))
    #            file.write("name=" + newName + "\n")
    #        else:
    #            file.write(line)
    #    file.truncate()

    #Delete folders that should no longer exist
    if os.path.exists(os.path.join(instanceDir, ".minecraft", "scripts")):
        shutil.rmtree(os.path.join(instanceDir, ".minecraft", "scripts"))
    if os.path.exists(os.path.join(instanceDir, ".minecraft", "resources")):
        shutil.rmtree(os.path.join(instanceDir, ".minecraft", "resources"))


    #Delete config folder and copy it over from extracted zip
    currInstanceFolderPath = os.path.join(instanceDir, ".minecraft", "config")
    currZipFolderPath = os.path.join(downloadDir, ".minecraft", "config")
    shutil.rmtree(currInstanceFolderPath)
    shutil.copytree(currZipFolderPath, currInstanceFolderPath)
        
    #Delete mods folder and copy it over from extracted zip
    currInstanceFolderPath = os.path.join(instanceDir, ".minecraft", "mods")
    currZipFolderPath = os.path.join(downloadDir, ".minecraft", "mods")
    shutil.rmtree(currInstanceFolderPath)
    shutil.copytree(currZipFolderPath, currInstanceFolderPath)
        
    if JAVA_17_21:
        #Delete some instance folders and files and copy them over from extracted zip
        currInstanceFolderPath = os.path.join(instanceDir, "mmc-pack.json")
        currZipFolderPath = os.path.join(downloadDir, "mmc-pack.json")
        if os.path.exists(currInstanceFolderPath):
            shutil.copy2(currZipFolderPath, currInstanceFolderPath)

        currInstanceFolderPath = os.path.join(instanceDir, "libraries")
        currZipFolderPath = os.path.join(downloadDir, "libraries")
        if os.path.exists(currInstanceFolderPath):
            shutil.rmtree(currInstanceFolderPath)
            shutil.copytree(currZipFolderPath, currInstanceFolderPath)
        
        currInstanceFolderPath = os.path.join(instanceDir, "patches")
        currZipFolderPath = os.path.join(downloadDir, "patches")
        if os.path.exists(currInstanceFolderPath):
            shutil.rmtree(currInstanceFolderPath)
            shutil.copytree(currZipFolderPath, currInstanceFolderPath)

    #Copy over other files from download (mainly language packs and changelogs)
    for file in os.listdir(os.path.join(downloadDir, ".minecraft")):
        filename = os.path.join(downloadDir, ".minecraft", file)
        if os.path.isfile(filename):
            shutil.copy2(filename, os.path.join(instanceDir, ".minecraft"))

    #Copy resourcepacks from download
    if COPY_RESOURCE_PACKS_FROM_DOWNLOAD:
        zipResourcepacksFolder = os.path.join(downloadDir, ".minecraft", "resourcepacks")
        if os.path.exists(zipResourcepacksFolder):
            for file in os.listdir(zipResourcepacksFolder):
                filename = os.path.join(zipResourcepacksFolder, file)
                if os.path.isfile(filename):
                    shutil.copy2(filename, os.path.join(instanceDir, ".minecraft", "resourcepacks"))

    #Overwrite config files specified in CONFIG_OVERWRITE_PATH file with ones from instance backup
    #This should smart combine files (i.e. actually combine the values present in both versions) instead of straight overwriting
    #Could be good for this to support folders, not just files
    #Maybe regex matching for easier use?
    configFiles = []
    if os.path.exists(CONFIG_OVERWRITE_PATH):
        with open(CONFIG_OVERWRITE_PATH, "r") as file:
            for line in file.readlines():
                stripped = line.strip()
                if stripped != "" and stripped[0] != "#":
                    replaced = stripped.replace("\\", "/")
                    split = replaced.split("/")
                    configFiles.append(os.path.join(*split))

        for file in configFiles:
            filename = os.path.join(".minecraft", "config", file)
            if os.path.exists(os.path.join(backupDir, filename)):
                shutil.copy2(os.path.join(backupDir, filename), os.path.join(instanceDir, filename))
            
    #Overwrite mods specified in MOD_OVERWRITE_PATH file with ones from instance backup
    #Ideally this would have regex matching so you dont have to worry about specific versions
    if os.path.exists(MOD_OVERWRITE_PATH):
        modFiles = []
        with open(MOD_OVERWRITE_PATH, "r") as file:
            for line in file.readlines():
                stripped = line.strip()
                if stripped != "" and stripped[0] != "#":
                    replaced = stripped.replace("\\", "/")
                    split = replaced.split("/")
                    modFiles.append(os.path.join(*split))

        for file in modFiles:
            filename = os.path.join(".minecraft", "mods", file)
            if os.path.exists(os.path.join(backupDir, filename)):
                shutil.copy2(os.path.join(backupDir, filename), os.path.join(instanceDir, filename))
                
    if DELETE_FILES_AFTER_UPDATE:
        shutil.rmtree(downloadDir)
        
    updateInstanceVersion(instanceID, newVersion)
    return True

def getMaxVersionLocal(currVersion):
    if os.path.exists(DOWNLOAD_DIRECTORY):
        maxVersion = currVersion
        maxVersionFilename = ""
        if not os.path.exists(os.path.join(DOWNLOAD_DIRECTORY, "files")):
            os.mkdir(os.path.join(DOWNLOAD_DIRECTORY, "files"))
        else:
            for file in os.listdir(os.path.join(DOWNLOAD_DIRECTORY, "files")):
                filename = os.path.join(DOWNLOAD_DIRECTORY, "files", file)
                if os.path.isdir(filename):
                    versionNum = getVersionNumberFromFileName(file, " ")
                    if (versionNum[0] > maxVersion[0]) or (versionNum[0] == maxVersion[0] and versionNum[1] > maxVersion[1]) or (versionNum[0] == maxVersion[0] and versionNum[1] == maxVersion[1] and versionNum[2] > maxVersion[2]):
                        maxVersion = versionNum
                        maxVersionFilename = filename
                    
        if not os.path.exists(os.path.join(DOWNLOAD_DIRECTORY, "zips")):
            os.mkdir(os.path.join(DOWNLOAD_DIRECTORY, "zips"))
        else:
            for file in os.listdir(os.path.join(DOWNLOAD_DIRECTORY, "zips")):
                filename = os.path.join(DOWNLOAD_DIRECTORY, "zips", file)
                if os.path.isfile(filename) and file.endswith(".zip"):
                    versionNum = getVersionNumberFromFileName(file)
                    if (versionNum[0] > maxVersion[0]) or (versionNum[0] == maxVersion[0] and versionNum[1] > maxVersion[1]) or (versionNum[0] == maxVersion[0] and versionNum[1] == maxVersion[1] and versionNum[2] > maxVersion[2]):
                        maxVersion = versionNum
                        maxVersionFilename = filename

        return maxVersion, maxVersionFilename
    else:
        os.mkdir(DOWNLOAD_DIRECTORY)
        os.mkdir(os.path.join(DOWNLOAD_DIRECTORY, "zips"))
        os.mkdir(os.path.join(DOWNLOAD_DIRECTORY, "files"))
        return currVersion, ""

#Returns highest version found or None if no version higher than currVersion is found
def localUpdate(instanceDir, instanceID, currVersion):
    maxVersion, maxVersionFilename = getMaxVersionLocal(currVersion)
    if maxVersionFilename != "":
        UIButtonTexts = [
            "Install update now",
            "Skip for now",
            "Permanently skip this update"]
        if os.path.isfile(maxVersionFilename):
            versionString = os.path.basename(maxVersionFilename).split("_")[3]
        else:
            versionString = os.path.basename(maxVersionFilename).split(" ")[3]
        userValue = promptUser("Version " + versionString + " available locally, what would you like to do?", UIButtonTexts)
        if userValue == 0:
            print("Installation started", flush = True)
            if updateInstance(instanceDir, maxVersionFilename, currVersion):
                print("Installation finished", flush = True)
            else:
                print("Error with installation")
        elif userValue == 1 or userValue == -1: #Is default
            print("Update being temporarly skipped")
        elif userValue == 2:
            updateInstanceVersion(instanceID, maxVersion)
            print("Update permanently skipped")

        return maxVersion

    return None

def getMaxVersionOnline(currVersion):
    maxVersion = currVersion
    maxVersionFilename = ""
    try:
        with requests.get(DOWNLOAD_LIST_URL) as response:
            if response.status_code != 200:
                return currVersion, ""

            for line in response.text.split("\n"):
                splitLine = line.strip().split("/")
                if splitLine[-2] == "betas":
                    continue

                filename = splitLine[-1]
                filenameSplit = filename.split("_")
                if (JAVA_17_21 == True and filenameSplit[-1] == "8.zip") or (JAVA_17_21 == False and filenameSplit[-1] == "17-21.zip"):
                    continue

                versionNum = getVersionNumberFromFileName(filename)
                if (versionNum[0] > maxVersion[0]) or (versionNum[0] == maxVersion[0] and versionNum[1] > maxVersion[1]) or (versionNum[0] == maxVersion[0] and versionNum[1] == maxVersion[1] and versionNum[2] > maxVersion[2]):
                    maxVersion = versionNum
                    maxVersionFilename = line.strip()

        return maxVersion, maxVersionFilename
    except:
        return currVersion, ""

def extractZip(zipPath):
    with zipfile.ZipFile(zipPath, "r", zipfile.ZIP_DEFLATED) as zip:
        #Get name of initial folder in zip file
        head, rootFolder = os.path.split(zip.namelist()[0])
        while head:
            head, rootFolder = os.path.split(head)

        if not os.path.exists(DOWNLOAD_DIRECTORY):
            os.mkdir(DOWNLOAD_DIRECTORY)
            os.mkdir(os.path.join(DOWNLOAD_DIRECTORY, "files"))
        elif not os.path.exists(os.path.join(DOWNLOAD_DIRECTORY, "files")):
            os.mkdir(os.path.join(DOWNLOAD_DIRECTORY, "files"))
            
        #Extract zip
        if not os.path.exists(os.path.join(DOWNLOAD_DIRECTORY, "files", rootFolder)):
            zip.extractall(os.path.join(DOWNLOAD_DIRECTORY, "files"))

        return os.path.join(DOWNLOAD_DIRECTORY, "files", rootFolder)
    return None

def downloadFile(URL, returnList = None):
    filename = URL.split("/")[-1].split("?")[0]
    if not os.path.exists(DOWNLOAD_DIRECTORY):
        os.mkdir(DOWNLOAD_DIRECTORY)
        os.mkdir(os.path.join(DOWNLOAD_DIRECTORY, "zips"))
    elif not os.path.exists(os.path.join(DOWNLOAD_DIRECTORY, "zips")):
        os.mkdir(os.path.join(DOWNLOAD_DIRECTORY, "zips"))
        
    zipPath = os.path.join(DOWNLOAD_DIRECTORY, "zips", filename)
    if not os.path.exists(zipPath):
        try:
            with requests.get(URL, stream = True) as response:
                with open(zipPath, "wb") as file:
                    for data in response.iter_content(chunk_size = DOWNLOAD_CHUNK_SIZE):
                        file.write(data)
        except:
            os.remove(zipPath)
            return
            
    downloadDir = extractZip(zipPath)
    if downloadDir == None:
        return

    if DELETE_ZIP_AFTER_DOWNLOAD:
        os.remove(zipPath)

    if returnList != None:
        returnList.append(downloadDir)

def main():
    if len(sys.argv) == 1:
        #Manual update
        print("It is recommended you close Prism before continuing")
        instanceDir = input("Directory of current GTNH instance: ")
        #Add first-time setup here if instanceDir is empty
        zipDir = input("Location of downloaded zip file: ")
        os.chdir(os.path.join(instanceDir, ".."))
        readConfig()
        print("Installation started", flush = True)
        if updateInstance(instanceDir, zipDir, [0,0,0]):   #oldVersion is set to nothing, not ideal but not much choice (maybe try to grab it from version.txt?)
            print("Installation finished")
        else:
            print("Error with installation")
    elif sys.argv[1] == "download":
        # Don't need to change directory here
        readConfig()
        downloadFile(sys.argv[2])
    elif sys.argv[1] == "auto":
        instanceID = os.environ["INST_ID"]
        instanceDir = os.environ["INST_DIR"]
        
        os.chdir(os.path.join(instanceDir, ".."))
        readConfig()

        currVersion = getInstanceVersion(instanceID)

        #check for downloaded update
        localUpdateFound = localUpdate(instanceDir, instanceID, currVersion)
        if localUpdateFound:
            currVersion = localUpdateFound
            if not CHECK_ONLINE_AFTER_LOCAL_UPDATE:
                exit(1)
        
        #check for update online
        maxVersion, maxVersionFilename = getMaxVersionOnline(currVersion)
        if maxVersionFilename != "":
            UIButtonTexts = [
                "Download and install update now",
                "Download in the background",
                "Skip for now",
                "Permanently skip this update"]
            userValue = promptUser("Version " + os.path.basename(maxVersionFilename).split("_")[3] + " available online, what would you like to do?", UIButtonTexts)
            if userValue == 0:
                #Download in thread
                downloadList = []
                t = threading.Thread(target=downloadFile, args=(maxVersionFilename, downloadList))
                t.start()
                print("Download started", flush = True)

                #Backup
                print("Backup started", flush = True)
                backupDir = createInstanceBackup(instanceDir, currVersion, maxVersion)
                if not backupDir:
                    print("Error with backup")
                else:
                    print("Backup finished")
                    t.join()
                    if len(downloadList) == 0:
                        print("Error with download")
                    else:
                        print("Download finished, installation started", flush = True)
                        if updateInstance(instanceDir, downloadList[0], currVersion, backupDir):
                            print("Installation finished")
                        else:
                            print("Error with installation")
            elif userValue == 1:
                #Start background download
                subprocess.Popen(PYTHON_EXECUTABLE + ' "' + AUTONH_PATH + '" download "' + maxVersionFilename + '"')
                print("Background download started")
            elif userValue == 2 or userValue == -1: #Is default
                print("Update being temporarly skipped")
            elif userValue == 3:
                updateInstanceVersion(instanceID, maxVersion)
                print("Update permanently skipped")
        elif not localUpdateFound:
            print("No update available, have fun :)")
    else:
        #Cmd line update
        instanceDir = sys.argv[1]
        zipDir = sys.argv[2]
        os.chdir(os.path.join(instanceDir, ".."))
        readConfig()
        print("Installation started", flush = True)
        if updateInstance(instanceDir, zipDir, [0,0,0]):   #oldVersion is set to nothing, not ideal but not much choice (maybe try to grab it from version.txt?)
            print("Installation finished")
        else:
            print("Error with installation")

if __name__ == "__main__":
    main()