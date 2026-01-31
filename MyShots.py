from Deadline.Scripting import *
from System import DateTime as DotNetDateTime
import os
import sys
import datetime
import getpass
import time
import threading
import subprocess
import winsound # Built-in Windows Sound
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# CONFIGURATION
# ==========================================
MY_USERNAME = getpass.getuser()
PORT_NUMBER = 8080 
CHECK_INTERVAL = 60 # Check every minute

# ==========================================
# NOTIFICATION SYSTEM (POWERSHELL)
# ==========================================
tracked_jobs = {} 

def show_windows_toast(title, message):
    """ 
    Uses PowerShell to generate a native Windows 10/11 notification 
    without needing external libraries or Admin rights.
    """
    try:
        # PowerShell script to create the XML notification
        ps_script = f"""
        $title = "{title}"
        $message = "{message}"
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode($title)) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode($message)) > $null
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Deadline Monitor")
        $notification = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier.Show($notification)
        """
        # Run disjointed so it doesn't block the python script
        subprocess.Popen(["powershell", "-Command", ps_script], creationflags=subprocess.CREATE_NO_WINDOW)
    except:
        pass

def background_status_checker():
    """ Background thread to check for finished jobs """
    print(f" [Notification Bot] Started. Checking every {CHECK_INTERVAL}s...")
    first_run = True

    while True:
        try:
            all_jobs = RepositoryUtils.GetJobs(True)
            current_ids = []

            for job in all_jobs:
                if job.JobUserName.lower() != MY_USERNAME.lower():
                    continue

                j_id = job.JobId
                j_name = job.JobName
                j_status = job.JobStatus 
                current_ids.append(j_id)

                if j_id in tracked_jobs:
                    old_status = tracked_jobs[j_id]
                    
                    if old_status != j_status and not first_run:
                        # --- STATUS CHANGED ---
                        if j_status == "Completed":
                            print(f" [Bot] Job Completed: {j_name}")
                            # 1. Play Sound
                            winsound.MessageBeep(winsound.MB_OK)
                            # 2. Show Windows Notification
                            show_windows_toast("Render Complete", f"{j_name} is finished.")
                        
                        elif j_status == "Failed":
                            print(f" [Bot] Job Failed: {j_name}")
                            winsound.MessageBeep(winsound.MB_ICONHAND)
                            show_windows_toast("Render FAILED", f"{j_name} has errors.")

                tracked_jobs[j_id] = j_status

            # Cleanup old jobs
            for old_id in list(tracked_jobs.keys()):
                if old_id not in current_ids:
                    del tracked_jobs[old_id]

            first_run = False
            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print(f" [Bot Error] {e}")
            time.sleep(CHECK_INTERVAL)

# ==========================================
# DEADLINE HELPER FUNCTIONS
# ==========================================

def get_duration_string(job):
    try:
        start_time = job.JobSubmitDateTime
        if job.JobStatus == "Completed":
            end_time = job.JobCompletedDateTime
            time_span = end_time.Subtract(start_time)
        else:
            time_span = DotNetDateTime.Now.Subtract(start_time)
        
        raw_str = time_span.ToString()
        if "." in raw_str: return raw_str.split(".")[0]
        return raw_str
    except: return "-"

def modify_job(action, job_id):
    try:
        job = RepositoryUtils.GetJob(job_id, True)
        if not job: return

        if action == "cancel":
            RepositoryUtils.SuspendJob(job)
        elif action == "complete":
            RepositoryUtils.CompleteJob(job)
    except: pass

# ==========================================
# WEB SERVER HANDLER
# ==========================================

class FarmMonitorHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        return # Silence console log spam

    def do_GET(self):
        if self.path.startswith("/action"):
            try:
                query = self.path.split('?')[1]
                params = dict(qc.split("=") for qc in query.split("&"))
                modify_job(params.get("type"), params.get("id"))
                self.send_response(303)
                self.send_header('Location', '/')
                self.end_headers()
                return
            except: pass

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        try:
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            all_jobs = RepositoryUtils.GetJobs(True)
            today = datetime.datetime.now().date()
            
            active_jobs_all = [] 
            my_jobs_today = []
            
            for job in all_jobs:
                status_lower = job.JobStatus.lower()
                
                if "rendering" in status_lower or "queued" in status_lower or "active" in status_lower:
                    active_jobs_all.append(job)
                
                if job.JobUserName.lower() == MY_USERNAME.lower():
                    job_date = job.JobSubmitDateTime.Date
                    if (job_date.Year == today.year and job_date.Month == today.month and job_date.Day == today.day):
                        my_jobs_today.append(job)
            
            active_jobs_all.sort(key=lambda x: x.JobSubmitDateTime, reverse=True)
            my_jobs_today.sort(key=lambda x: x.JobSubmitDateTime, reverse=True)
            my_jobs_today = my_jobs_today[:10]

            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Farm Monitor</title>
                <style>
                    body {{ font-family: 'Segoe UI', sans-serif; background: #1e1e1e; color: #ccc; padding: 20px; }}
                    .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #444; padding-bottom: 15px; margin-bottom: 20px; }}
                    h1 {{ margin: 0; color: #eee; font-size: 20px; }}
                    .user-badge {{ background: #333; padding: 4px 8px; border-radius: 4px; font-size: 12px; color: #888; margin-left: 10px; }}
                    .btn-refresh {{ background-color: #007acc; color: white; border: none; padding: 8px 25px; font-size: 14px; border-radius: 4px; text-decoration: none; font-weight: bold; transition: 0.2s; }}
                    .btn-refresh:hover {{ background-color: #005f9e; }}
                    h2 {{ color: #eee; font-size: 16px; margin-top: 30px; border-left: 4px solid #555; padding-left: 10px; }}
                    table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 20px; background: #252526; }}
                    th {{ text-align: left; background: #333; color: #aaa; padding: 10px; }}
                    td {{ border-bottom: 1px solid #444; padding: 8px 10px; vertical-align: middle; }}
                    .st-Rendering, .st-Active {{ color: #8bc34a; font-weight: bold; }}
                    .st-Queued {{ color: #d69d36; }}
                    .st-Completed {{ color: #666; text-decoration: line-through; }}
                    .st-Failed {{ color: #f44336; }}
                    .st-Suspended {{ color: #d63636; }}
                    .p-container {{ background: #444; width: 60px; height: 5px; border-radius: 4px; overflow: hidden; display: inline-block; margin-right: 10px; vertical-align: middle; }}
                    .p-fill {{ height: 100%; background: #007acc; }}
                    .st-Rendering .p-fill, .st-Active .p-fill {{ background: #8bc34a; }}
                    .st-Queued .p-fill {{ background: #d69d36; }}
                    .empty {{ padding: 20px; text-align: center; color: #555; font-style: italic; }}
                    .mine {{ background: #2d353b; }} .mine td {{ color: #fff; }}
                    .btn-action {{ padding: 3px 8px; font-size: 10px; margin-right: 4px; border-radius: 3px; border: none; cursor: pointer; color: white; }}
                    .btn-cancel {{ background: #c62828; }} .btn-cancel:hover {{ background: #8e0000; }}
                    .btn-complete {{ background: #455a64; }} .btn-complete:hover {{ background: #263238; }}
                </style>
                <script>
                    function confirmAction(url, actionName) {{ if(confirm("Are you sure you want to " + actionName + "?")) {{ window.location.href = url; }} }}
                </script>
            </head>
            <body>
                <div class="header">
                    <div><h1>Deadline Monitor <span class="user-badge">{MY_USERNAME}</span></h1></div>
                    <div><span style="font-size:12px; color:#666; margin-right:15px">Last Check: {timestamp}</span><a href="/" class="btn-refresh">REFRESH</a></div>
                </div>

                <h2><span class="section-icon">&#128100;</span> My History (Today - Last 10)</h2>
                <table>
                    <thead><tr><th>Job Name</th><th>Status</th><th>Progress</th><th>Submitted</th><th>Duration</th></tr></thead>
                    <tbody>
            """
            if len(my_jobs_today) == 0: html += "<tr><td colspan='5' class='empty'>No submissions today.</td></tr>"

            for job in my_jobs_today:
                percent = 0
                if job.JobTaskCount > 0: percent = int((float(job.CompletedChunks) / float(job.JobTaskCount)) * 100)
                
                s_lower = job.JobStatus.lower()
                status_css = "Queued"
                if "rendering" in s_lower or "active" in s_lower: status_css = "Rendering"
                elif "completed" in s_lower: status_css = "Completed"
                elif "failed" in s_lower: status_css = "Failed"
                elif "suspended" in s_lower: status_css = "Suspended"

                html += f"""<tr><td>{job.JobName}</td><td class="st-{status_css}">{job.JobStatus}</td><td><div class='p-container'><div class='p-fill' style='width:{percent}%'></div></div>{percent}%</td><td>{job.JobSubmitDateTime.ToString("HH:mm")}</td><td>{get_duration_string(job)}</td></tr>"""
            
            html += """</tbody></table>
                <h2><span class="section-icon">&#128293;</span> Active Queue & Renders</h2>
                <table><thead><tr><th>User</th><th>Job Name</th><th>Status</th><th>Progress</th><th>Submitted</th><th>Duration</th><th>Actions</th></tr></thead><tbody>"""
            
            if len(active_jobs_all) == 0: html += "<tr><td colspan='7' class='empty'>The farm is completely empty!</td></tr>"
            
            for job in active_jobs_all:
                percent = 0
                if job.JobTaskCount > 0: percent = int((float(job.CompletedChunks) / float(job.JobTaskCount)) * 100)
                
                s_lower = job.JobStatus.lower()
                status_css = "Queued"
                if "rendering" in s_lower or "active" in s_lower: status_css = "Rendering"
                
                row_class, actions_html = "", ""
                if job.JobUserName.lower() == MY_USERNAME.lower(): 
                    row_class = "mine"
                    actions_html = f"""<button class="btn-action btn-cancel" onclick="confirmAction('/action?type=cancel&id={job.JobId}', 'STOP/SUSPEND this job')">Stop</button><button class="btn-action btn-complete" onclick="confirmAction('/action?type=complete&id={job.JobId}', 'Mark as COMPLETE')">&#10003;</button>"""
                
                html += f"""<tr class='{row_class}'><td style="font-weight:bold;">{job.JobUserName}</td><td>{job.JobName}</td><td class="st-{status_css}">{job.JobStatus}</td><td><div class='p-container'><div class='p-fill' style='width:{percent}%'></div></div>{percent}%</td><td>{job.JobSubmitDateTime.ToString("HH:mm")}</td><td>{get_duration_string(job)}</td><td>{actions_html}</td></tr>"""

            html += "</tbody></table></body></html>"
            self.wfile.write(html.encode("utf-8"))
            
        except Exception as e:
            self.wfile.write(f"<h3>Python Error:</h3><pre>{str(e)}</pre>".encode("utf-8"))

def __main__( *args ):
    print("=================================================")
    print(f" LOGGED IN AS: {MY_USERNAME}")
    print(" MONITOR SERVER RUNNING")
    print(" ALERTS: WINDOWS POPUPS + SOUND")
    print("=================================================")

    # START NOTIFICATION THREAD
    t = threading.Thread(target=background_status_checker)
    t.daemon = True
    t.start()

    try: os.startfile(f"http://localhost:{PORT_NUMBER}")
    except: pass

    server_address = ('', PORT_NUMBER)
    httpd = HTTPServer(server_address, FarmMonitorHandler)
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
    httpd.server_close()
