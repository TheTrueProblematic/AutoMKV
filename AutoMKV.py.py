from tkinter import *
import subprocess
import os
import random
import psutil
import time
import boto3
import threading
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Initialize status variable
guiStatus = 1
NotificationLevel = 1
running = False
recordTime = time.time()

def levelSetError():
    print("Level Set Error")

# function to set notification level
def setLevel(level):
    global guiStatus
    global NotificationLevel
    if guiStatus != 2:
        print(f"Notification level set to {level}")
        guiStatus = 5
        NotificationLevel = level
        update_status()
    else:
        levelSetError()

# function to handle Start button click
def start():
    global guiStatus
    global running
    running = True
    # print("-- Start --")
    guiStatus = 7
    update_status()

# function to handle Stop button click
def stop():
    global guiStatus
    global running
    running = False
    guiStatus = 4
    update_status()

# function to update the status message


def find_text_after_search(search, text):
    # Find the start of the search term in the text
    start_index = text.find(search)
    if start_index == -1:
        # If the search term is not found, return an empty string
        return ""

    # Move the start index to the end of the search term
    start_index += len(search)

    # Find the double quote character after the search term
    end_index = text.find('"', start_index)
    if end_index == -1:
        # If the double quote is not found, return an empty string
        return ""

    # Return the substring between the end of search term and the double quote
    return text[start_index:end_index]


def randDelete(folder_path):
    # Get the list of all files in the folder
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

    # Check if there is more than one file in the folder
    if len(files) <= 1:
        print("ERROR: The folder must contain more than one file.")
        completed(False)
        return

    # Randomly select one file to keep
    file_to_keep = random.choice(files)
    print(f"Keeping file: {file_to_keep}")

    # Delete all other files in the folder
    for file in files:
        if file != file_to_keep:
            file_path = os.path.join(folder_path, file)
            os.remove(file_path)
            print(f"Deleted file: {file}")


def deleteSpares(path):
    # List all files in the given directory
    try:
        files = [os.path.join(path, file) for file in os.listdir(path) if os.path.isfile(os.path.join(path, file))]
    except FileNotFoundError:
        print("The specified path does not exist.")
        return 0

    if len(files) == 1:
        # Only one file in the folder, do nothing
        return 1
    elif len(files) > 1:
        # Find the largest file by size
        largest_files = sorted(files, key=lambda x: os.path.getsize(x), reverse=True)
        max_size = os.path.getsize(largest_files[0])

        # Filter out files that are the largest if there are multiple
        largest_files = [file for file in largest_files if os.path.getsize(file) == max_size]

        # Delete all other files
        files_to_delete = [file for file in files if file not in largest_files]
        for file in files_to_delete:
            os.remove(file)

        return len(largest_files)


def awaitNew():
    print("Processing complete. Waiting for disk to be ejected...")
    drive_letter = 'D:'
    while is_bluray_drive(drive_letter):
        time.sleep(5)  # Check every 5 seconds
    print("Disk ejected. Ready for a new disk.")


def spaceUnderscore(input_string):
    return input_string.replace(' ', '_')


def underscoreSpace(input_string):
    return input_string.replace('_', ' ')


def renameFile(folder_path, name):
    # Check if the given path is a directory
    if not os.path.isdir(folder_path):
        return False

    # List all files in the folder
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

    # Check if there is exactly one file in the folder
    if len(files) != 1:
        return False

    # Get the full path of the single file
    file_path = os.path.join(folder_path, files[0])
    # Create the new file path with the given name
    new_file_path = os.path.join(folder_path, name)

    # Rename the file
    os.rename(file_path, new_file_path)

    return True


def completed(success, title):
    global NotificationLevel
    if success:
        print("Completed successfully.")
        notify(True, title, NotificationLevel)
        awaitNew()
    else:
        print("Failed to complete successfully.")
        notify(False, title, NotificationLevel)
        awaitNew()


def processFile():
    global guiStatus
    print("Disk inserted. Processing files...")

    guiStatus = 3
    update_status()

    loc = 'T:/Shared/MoviesTBC'

    driveCmd = '"C:/Program Files (x86)/MakeMKV/makemkvcon64.exe" -r info disk:0'

    result = subprocess.run(driveCmd, shell=True, text=True, capture_output=True)

    fullTxt = result.stdout

    print("Drive List:")
    print(result.stdout)

    searchTerm = '1WL","'

    title = find_text_after_search(searchTerm, fullTxt)

    title = underscoreSpace(title)

    workFold = loc + '/' + spaceUnderscore(title)

    print(f"Title: {title}")
    print(f"Work Folder: {workFold}")

    os.makedirs(workFold, exist_ok=True)

    ripAll = '"C:/Program Files (x86)/MakeMKV/makemkvcon64.exe" mkv disc:0 all ' + workFold
    # ripAll = '"C:/Program Files (x86)/MakeMKV/makemkvcon64.exe" mkv disc:0 all --minlength=5000 --progress=1 --out="'+workFold+'"'

    result2 = subprocess.run(ripAll, shell=True, text=True, capture_output=True)

    print("Rip Report:")
    print(result2.stdout)

    # Check the return code to see if the process was successful
    if result2.returncode == 0:
        print("Rip was successful.")
    else:
        print("Rip failed with return code:", result2.returncode)
        completed(False, title)
        return

    numFiles = deleteSpares(workFold)

    if numFiles != 1:
        print(numFiles + " files remain...Deleting Randomly")
        randDelete(workFold)

    titlefile = title + ".mkv"

    if renameFile(workFold, titlefile):
        completed(True, title)
        return
    else:
        completed(False, title)
        return


class DiskHandler(FileSystemEventHandler):
    def on_created(self, event):
        # Call the processFile function when a disk is inserted
        processFile()


def is_bluray_drive(drive):
    try:
        usage = psutil.disk_usage(drive)
        return True
    except:
        return False


def send_email_aws_ses(message, subject, recipient):
    # Create a new SES resource and specify a region.
    ses_client = boto3.client('ses', region_name='us-west-2')  # Replace with your region

    try:
        # Provide the contents of the email.
        response = ses_client.send_email(
            Source='MKV.Notifications@passpals.net',  # Replace with your verified email
            Destination={
                'ToAddresses': [recipient],
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': message,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        print("Email sent! Message ID:"),
        print(response['MessageId'])

    except NoCredentialsError:
        print("Credentials not available")
    except PartialCredentialsError:
        print("Incomplete credentials")
    except Exception as e:
        print("Error sending email: ", e)


def notify(status, title, level):
    # Will send everyone a status at 1, just matt at 2 and just max at 3

    matt = '7203014754@tmomail.net'
    maxn = '7206447060@vtext.com'
    succ = title + " was ripped successfully!"
    fail = title + " failed."

    if level == 1:
        if status:
            send_email_aws_ses(succ, "Status", matt)
            send_email_aws_ses(succ, "Status", maxn)
        else:
            send_email_aws_ses(fail, "Status", matt)
            send_email_aws_ses(fail, "Status", maxn)

    elif level == 2:
        if status:
            send_email_aws_ses(succ, "Status", matt)
        else:
            send_email_aws_ses(fail, "Status", matt)

    elif level == 3:
        if status:
            send_email_aws_ses(succ, "Status", maxn)
        else:
            send_email_aws_ses(fail, "Status", maxn)


# create root window
root = Tk()

# root window title and dimension
root.title("Auto MKV")
# Set geometry(widthxheight)
root.geometry('700x600')


# adding menu bar in root window
menu = Menu(root)
item = Menu(menu, tearoff=0)
item.add_command(label='Max', command=lambda: setLevel(3))
item.add_command(label='Matt', command=lambda: setLevel(2))
item.add_command(label='Both', command=lambda: setLevel(1))
menu.add_cascade(label='Notifications', menu=item)
root.config(menu=menu)

# adding a large title to the root window
title = Label(root, text="Auto MKV", font=("Arial", 40), fg="#003366")
title.grid(column=0, row=0, columnspan=3, pady=30)

# creating a frame to hold the buttons
button_frame = Frame(root)
button_frame.grid(column=0, row=1, columnspan=3, pady=30)

# adding Stop and Start buttons to the frame
stop_btn = Button(button_frame, text="Stop", fg="red", bg="black", font=("Arial", 24), width=10, height=2, command=stop)
stop_btn.pack(side=LEFT, padx=20)

start_btn = Button(button_frame, text="Start", fg="green", bg="black", font=("Arial", 24), width=10, height=2, command=start)
start_btn.pack(side=RIGHT, padx=20)

# adding a status window below the buttons
status_frame = Frame(root, bd=2, relief="solid")
status_frame.grid(column=0, row=2, columnspan=3, padx=50, pady=30, sticky="ew")

status_label = Label(status_frame, text="", font=("Arial", 18), padx=10, pady=10)
status_label.pack(fill="both", expand=True)

# Set columns to be stretchable
root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)
root.grid_columnconfigure(2, weight=1)

# Set rows to be stretchable
root.grid_rowconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)
root.grid_rowconfigure(2, weight=1)


def update_status():
    global guiStatus
    # print("-- Update Status --")
    messages = {
        1: "Ready",
        2: "Running...",
        3: "Disk inserted. Processing files...",
        4: "Stopping...",
        5: "Notification Status Updated",
        6: "This is a longer message to make sure that a longer message can still fit.",
        7: "Starting..."
    }
    status_label.config(text=messages.get(guiStatus, "Unknown status"))

update_status()

def gui():
    root.mainloop()


def loop():
    global running
    global guiStatus
    global recordTime
    delayCheck = True

    # Path to monitor
    drive_letter = 'D:'

    print("Monitoring started. Waiting for disk insertion...")

    try:
        # Continuously check if the drive is a Blu-ray drive and is ready
        while True:
            # print("-- While Loop --")
            if running:
                guiStatus = 2
                if is_bluray_drive(drive_letter):
                    print(f"{drive_letter} is a Blu-ray drive and is ready. Processing disk...")
                    time.sleep(20)
                    processFile()
                    print("Waiting for next disk...")
                else:
                    print("No disk inserted. Checking again in 10 seconds.")
                time.sleep(10)
            else:
                # print("-- Else Started --")
                if guiStatus == 5:
                    if delayCheck:
                        recordTime = time.time()
                        delayCheck = False
                    else:
                        passed = time.time() - recordTime
                        if passed > 5:
                            delayCheck = True
                            guiStatus = 1
                            update_status()
                else:
                    guiStatus = 1
                    update_status()
                time.sleep(1)
            update_status()


    except KeyboardInterrupt:
        print("Monitoring interrupted by user.")
    finally:
        print("AutoMKV stopped.")



def main():
    global running
    global guiStatus
    global recordTime
    # Execute Tkinter
    try:
        t1 = threading.Thread(target=loop, args=())
        t1.start()
        gui()
        t1.join()
    except KeyboardInterrupt:
        print("Monitoring interrupted by user.")
    finally:
        print("AutoMKV stopped.")

    # delayCheck = True
    #
    # # Path to monitor
    # drive_letter = 'D:'
    #
    # print("Monitoring started. Waiting for disk insertion...")
    #
    # try:
    #     # Continuously check if the drive is a Blu-ray drive and is ready
    #     while True:
    #         print("-- While Loop --")
    #         if running:
    #             guiStatus = 2
    #             if is_bluray_drive(drive_letter):
    #                 print(f"{drive_letter} is a Blu-ray drive and is ready. Processing disk...")
    #                 time.sleep(20)
    #                 processFile()
    #                 print("Waiting for next disk...")
    #             else:
    #                 print("No disk inserted. Checking again in 10 seconds.")
    #             time.sleep(10)
    #         else:
    #             print("-- Else Started --")
    #             if guiStatus == 5:
    #                 if delayCheck:
    #                     recordTime = time.time()
    #                     delayCheck = False
    #                 else:
    #                     passed = time.time() - recordTime
    #                     if passed > 5:
    #                         delayCheck = True
    #                         guiStatus = 1
    #                         update_status()
    #             else:
    #                 guiStatus = 1
    #                 update_status()
    #             time.sleep(1)
    #         update_status()
    #
    #
    # except KeyboardInterrupt:
    #     print("Monitoring interrupted by user.")
    # finally:
    #     print("AutoMKV stopped.")
    #     t1.join()


if __name__ == "__main__":
    main()

