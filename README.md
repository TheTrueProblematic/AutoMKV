# Auto MKV

A Tkinter GUI that monitors a Windows optical drive and uses MakeMKV to rip Blu ray content to MKV. It creates a per title folder, keeps a single MKV, renames it to the detected title, and can send success or failure notifications through AWS SES.

## Features

* Start and Stop controls in a GUI titled Auto MKV
* Live status label that updates as the workflow runs
* Polling based detection of drive readiness on a Windows drive letter using `psutil`
* Drive interrogation and ripping via MakeMKV command line
* Output organized in a per title folder
* Automatic pruning to a single MKV file
* Final rename to `<Title>.mkv`
* Optional notifications sent through AWS SES
* Waits for the disc to be ejected before becoming ready for a new disc

## How it works

1. The GUI launches with a large title and two buttons labeled Start and Stop, plus a Notifications menu.
2. When you click Start, a background thread begins polling the configured optical drive letter. The check considers the drive ready if `psutil.disk_usage('<drive>:')` does not raise.
3. On readiness, the code runs  
   `"<MakeMKV path>\makemkvcon64.exe" -r info disk:0`  
   and parses the title by reading the substring after `1WL","` up to the next double quote. Underscores in the parsed title are converted to spaces for display, and spaces are then converted to underscores for the working folder name.
4. A working folder is created at `<output_base>/<Title_with_underscores>`.
5. The rip uses  
   `"<MakeMKV path>\makemkvcon64.exe" mkv disc:0 all <working_folder>`.
6. After ripping, the code keeps only the largest file or files by size in the working folder. If more than one largest file remains, one file is chosen at random to keep and the rest are deleted.
7. The single remaining file is renamed to `<Title>.mkv`. Success or failure triggers a notification.
8. The app prints that processing is complete and waits until the drive is no longer accessible before returning to a ready state.

## Requirements

* Python standard library modules used by this script  
  tkinter, subprocess, os, random, time, threading
* Third party modules used by this script  
  `psutil`, `boto3`, `botocore`, `watchdog`
* MakeMKV command line present at  
  `C:/Program Files (x86)/MakeMKV/makemkvcon64.exe`
* A Windows system with an optical drive accessible at a drive letter
* AWS credentials configured for `boto3` if you want notifications to send through SES

## Notifications

* SES region is set in code to `us-west-2`.
* Sender and recipient addresses are hardcoded in the script and can be changed in the `notify` and `send_email_aws_ses` functions. This README does not list those addresses.
* Behavior by level  
  Level 1 sends to both recipients  
  Level 2 sends to one recipient  
  Level 3 sends to the other recipient
* Message bodies  
  Success uses `<Title> was ripped successfully!`  
  Failure uses `<Title> failed.`  
  Subject is `Status`.

If AWS credentials are missing or incomplete, the script prints `Credentials not available` or `Incomplete credentials` and will print any other exception raised by `boto3.client('ses').send_email`.

## Status messages

The status label shows one of these messages based on an internal numeric state.

* 1 shows Ready
* 2 shows Running...
* 3 shows Disk inserted. Processing files...
* 4 shows Stopping...
* 5 shows Notification Status Updated
* 6 shows This is a longer message to make sure that a longer message can still fit.
* 7 shows Starting...
* Any unknown code shows Unknown status

## Configuration in code

* Drive letter used for monitoring and eject wait is hardcoded
* Output base directory is hardcoded
* MakeMKV CLI paths used for info and rip  
  `"...\makemkvcon64.exe" -r info disk:0`  
  `"...\makemkvcon64.exe" mkv disc:0 all <working_folder>`
* SES region and email sender and recipients are hardcoded

## Internal structure

* The GUI runs on the main thread via `Tk().mainloop()`.
* A background thread executes a `while True` loop that updates status, checks `running`, polls the drive, and calls `processFile()`.
* Title parsing uses `find_text_after_search('1WL","', fullTxt)` where `fullTxt` is `makemkvcon64.exe -r info disk:0` output.
* Folder naming uses `spaceUnderscore` to replace spaces with underscores for the working folder name, and file renaming uses `<Title>.mkv` where `<Title>` is the parsed title after converting underscores to spaces.
* Notification level changes print `Notification level set to <level>` and update the status to `Notification Status Updated` unless the current status is the code for Running, which triggers `Level Set Error` to be printed.

## Known limitations and notes

* The check for a Blu ray disc is based on whether `psutil.disk_usage('<drive>:')` succeeds. It does not validate media type.
* Path locations and the MakeMKV executable path are hardcoded to Windows specific values as shown above.
* `watchdog` is imported and a `DiskHandler` class exists, but no `Observer` is started and no handler is registered. Drive detection is polling based.
* `completed(success, title)` is defined to take two arguments, but `randDelete` calls `completed(False)` with one argument in the case where there is zero or one file. That call site does not match the function signature.
* In `processFile`, when more than one file remains after `deleteSpares`, the line `print(numFiles + " files remain...Deleting Randomly")` concatenates an integer with a string. That expression will raise a `TypeError` if executed.
* The title parsing depends on the presence of the exact substring `1WL","` in the `makemkvcon64.exe -r info disk:0` output. If it is not found, the title will be an empty string.

## Running

1. Ensure MakeMKV is installed at `C:/Program Files (x86)/MakeMKV/makemkvcon64.exe`.
2. Ensure the optical drive letter used in the script exists and is accessible, and the configured output path exists or can be created.
3. Optionally configure AWS credentials for SES if you want notifications to send.
4. Run the script with Python. Click Start to begin monitoring and Stop to stop.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
