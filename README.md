# Auto MKV Blu-ray Ripper

## Overview
Auto MKV is a Python application that automates ripping Blu-ray discs using MakeMKV and manages the resulting video files. It provides a simple graphical interface built with Tkinter and supports sending notifications about the ripping process through Home Assistant. The application is designed to run continuously, monitor a Blu-ray drive for inserted discs, and handle the entire ripping process with minimal user interaction.

## How It Works
1. The application monitors a specified Blu-ray drive for inserted discs.
2. When a disc is detected, it uses MakeMKV to retrieve disc information and rip all titles.
3. It processes the ripped files by keeping only the largest file (or selecting one at random if necessary).
4. The final file is renamed to match the disc title and saved in the configured destination folder.
5. Notifications about the success or failure of the rip are sent to Home Assistant mobile app notification services.

The user interface allows you to start and stop monitoring, set the notification level (send to both users, Matt only, or Max only), and view status messages.

## Requirements
- Windows environment with MakeMKV installed
- Python 3.10 or newer
- Installed Python dependencies:
  - `psutil`
  - `requests`
- A Home Assistant instance with mobile app notify entities configured:
  - `notify.mobile_app_prometheus` (Matt)
  - `notify.mobile_app_promaxeus` (Max)

## Environment Variables
The application uses two environment variables for Home Assistant integration:
- `HOME_ASSISTANT_BASE_URL` (example: `http://homeassistant.local:8123`)
- `HOME_ASSISTANT_TOKEN` (a long-lived access token created in your Home Assistant user profile)

These variables must be set before running the application.

## setup_ha.bat
To simplify configuration of the required environment variables, the project includes the `setup_ha.bat` script. This script allows you to configure the values once and store them permanently in the Windows environment.

### Features
- Displays current values if they are already set.
- Prompts whether to override or keep the existing values.
- Lets you choose whether to store values for the current user or system-wide (administrator privileges required for system-wide).
- Updates the Windows environment permanently so you do not need to set the variables manually each time.

### Usage
1. Run `setup_ha.bat` by double clicking it or executing it in Command Prompt.
2. Choose whether to set values for the current user or system-wide.
3. Review existing values if present. Choose to override or keep them.
4. Enter new values when prompted.
5. The script will update the environment and broadcast the change so new shells can see it immediately.

After running the script, open a new Command Prompt or PowerShell window and run your Auto MKV application. It will automatically use the configured Home Assistant connection.

## Running Auto MKV
1. Ensure MakeMKV is installed and the path to `makemkvcon64.exe` is correct in the Python script.
2. Run the Python script:
   ```bash
   python automkv.py
   ```
3. Insert a Blu-ray disc into the specified drive.
4. The application will automatically rip and process the disc, then send notifications based on the configured level.