import requests
import json
import os
import sys
import psutil
import signal
import time
import datetime
import subprocess
from slackclient import SlackClient
from datetime import datetime

'''
    Script for managing CastXMR miner.
    This script has the ability to auto restarting the CastXMR miner when :
    1. The hashrate falls below the configured amount
    2. Low accepted share rate in certain duration
    3. Not all GPU initialized properly
    4. Script cannot contact miner via the port API

    It has the ability to contact Slack and reports the status of the miner

    Dependencies
    1. Python 2.7
    2. Python - SlackClient
    3. Python - SlackUtil
    4. CastXMR
    5. OverdriveNTool

    Installation
    1. Install python normally
    2. Invoke :
        pip install psutil slackclient requests datetime
    3. Configure the script
    4. Run the script - if its ok, set it to auto run during boot time.

'''


# Define the boxname
BoxName='MyAwesomeMinerBox'

# Define where the cast_xmr executable location
MinerFolder = 'C:\Users\{My Username}\Desktop\Miner\cast_xmr'

# Define the right cast_xmr invocation command, don't change the api remote port if possible
# Consult the CastXMR for proper arguments
MinerCommand = 'cast_xmr-vega.exe --intensity=-1 -O -1 -G 0,1,2,3,4,5 -R 8181 -S {Pool address}:{Pool Port} -u {My Wallet}'

# Define the miner remote address
MinerRemoteAddress = 'http://127.0.0.1:7777'

# Define the minimum hashrate that will cause the script to restart the miner
MinHashRate = "8400000";

# Define the OverDriveTool folder
OverDriveFolder = 'C:\Users\{My Username}\Desktop\Miner'

# Define the command for the overdrive tools
OverDriveCommand = 'OverdriveNTool.exe -r1 -r2 -r3 -r4 -r5 -r6 -p1Vega56N -p2Vega56N -p3Vega56N -p4Vega56N -p5Vega56N -p6Vega56N'

# Define the slack username
SlackUser="{My Slack Username}"

# Define the slack channel to post the miner message
SlackChannel="#{My Slack Channel}"

# Define the slack token for connecting to slack
SlackToken="{My Slack Token}"


'''
    Applying GPU settings, Currently only applying OverDrive Tools.
    If you are using AMD BlockChain Driver, you might need to add restart GPU here
'''
def applySettings():
    print 'Applying GPU settings'
    sendSlack('%s applying GPU settings' % (BoxName))
    return subprocess.Popen('%s\%s' % (OverDriveFolder, OverDriveCommand), cwd=OverDriveFolder)


'''
    Starting Miner
'''
def startMiner():
    env = os.environ.copy()

    # python env wants string instead of int!
    # This can be customized to fit user machine specs
    env['GPU_FORCE_64BIT_PTR'] = '1'
    env['GPU_MAX_HEAP_SIZE'] = '100'
    env['GPU_USE_SYNC_OBJECTS'] = '1'
    env['GPU_MAX_ALLOC_PERCENT'] = '100'
    env['GPU_SINGLE_ALLOC_PERCENT'] = '100'

    environment = env
    print 'Starting CastXMR instance'

    sendSlack('%s Starting Miner Instance' % (BoxName))
    return subprocess.Popen('%s\%s' % (MinerFolder, MinerCommand), env=environment, cwd=MinerFolder)


'''
    Killing miner using psutil
'''
def killMiner():
    print 'Stoping CastXMR'
    sendSlack('%s Stopping Miner Instance' % (BoxName))
    for proc in psutil.process_iter():
        if proc.name() == "cast_xmr-vega.exe":
            proc.kill()


'''
    Sending message to slack
'''
def sendSlack(message):
    if message:
        try:
            s = SlackClient(SlackToken)
            output = "[{0}] {1}".format(datetime.now().strftime('%m-%d %H:%M'), message)
            s.api_call(
                 "chat.postMessage",
                 channel=SlackChannel,
                 text=output
             )
        except:
            pass


'''
    Restarting miner instance
'''
def restart():
    killMiner()
    applySettings()
    startMiner()



'''
    Stopping miner instance
'''
def shutdown(signal, number):
    killMiner()


'''
    Rebooting machine
'''
def reboot():
    killMiner()
    subprocess.call(["shutdown", "/r", "/t", "5"])
    sys.exit()


'''
    Main Loop
'''
def main():

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    minute    = 0
    shares    = 0
    restarted = 0

    restart()
    while True:
        time.sleep(2)
        if restarted > 5:
            sendSlack('Rebooting box because failed to initialize miner or gpu properly')
            reboot()
            break
        try:
            request = requests.get(MinerRemoteAddress)
            if request.status_code is not 200:
                restarted += 1
                restart()
            else:
                break

        except:
            restarted += 1
            restart()

    time.sleep(30)

    while True:

        try:
            request = requests.get(MinerRemoteAddress)
            if request.status_code is 200:
                data = json.loads(request.text)

                # Check hashrate every 1 minute
                if data and data.get('total_hash_rate', False):
                    if int(MinHashRate) > int(data.get('total_hash_rate')):
                        sendSlack('Restarting miner due to low hashrate detected')
                        restart()

                # Check number of shares every 20 minutes
                minute = minute + 1
                if minute is 20:
                    if int(shares) == int(data['shares']['num_accepted']):
                        sendSlack('Restarting miner due to low shares detected')
                        restart()
                    else:
                        shares = data['shares']['num_accepted']
                        minute = 0;


            if request.status_code is not 200:
                sendSlack('Restarting miner due to invalid server request detected')
                restart()


        except:
            restart()

        time.sleep(60)


if __name__ == "__main__":
    main()

os.system('pause')
