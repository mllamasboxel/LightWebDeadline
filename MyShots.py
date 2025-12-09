from Deadline.Scripting import *
import os
import sys
import time
import datetime

# ==========================================
# CONFIGURATION
MY_USERNAME = "manuel.llamas"
REFRESH_SECONDS = 5
# ==========================================

def get_eta_string(job):
    """
    Fetches the pre-calculated ETA directly from Deadline.
    """
    status = job.JobStatus.lower()
    
    # If not Active/Rendering, there is no ETA
    if "active" not in status and "rendering" not in status:
        return "<span style='color:#555'>-</span>"

    try:
        # Get the internal .NET TimeSpan object
        # This matches the "Estimated Remaining Render Time" column in Monitor
        time_remaining = job.JobEstimatedWallClockTimeRemaining
        
        # Convert .NET object to string (Format: dd.hh:mm:ss)
        time_str = time_remaining.ToString()
        
        # CLEANUP:
        # If Deadline doesn't know yet, it returns a massive number of days
        if "10675199" in time_str: 
            return "<span style='color:#777'>Calculating...</span>"
            
        # If it returns 00:00:00, it's either done or just starting
        if time_str.startswith("00:00:00") and job.JobProgress < 100:
             # Check if it really is 0 or just small
             pass

        # Remove milliseconds (anything after the last dot) to make it readable
        # "00:15:30.450000" -> "00:15:30"
        if "." in time_str:
            parts = time_str.split(".")
            # handle case where day is separated by dot (d.hh:mm:ss) vs seconds (ss.ms)
            if len(parts) > 1 and len(parts[-1]) > 3: 
                time_str = parts[0]

        return time_str

    except:
        return "?"

def __main__( *args ):
    print("=================================================")
    print(" LIVE MONITOR: Queue + Fixed ETA")
    print(" Updating every " + str(REFRESH_SECONDS) + " seconds...")
    print(" Leave this window OPEN.")
    print("=================================================")

    first_run = True
    output_file = os.path.join(os.path.dirname(__file__), "LiveStatus.html")

    while True:
        try:
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            print("[" + timestamp + "] Fetching jobs...")
            
            all_jobs = RepositoryUtils.GetJobs(True)
            today = datetime.datetime.now().date()
            
            active_jobs_all = [] 
            my_jobs_today = []
            
            for job in all_jobs:
                status_lower = job.JobStatus.lower()

                # --- LIST 1: GLOBAL ACTIVE ---
                if ("rendering" in status_lower or 
                    "queued" in status_lower or 
                    "active" in status_lower):
                    active_jobs_all.append(job)
                
                # --- LIST 2: MY JOBS (Today) ---
                if job.JobUserName.lower() == MY_USERNAME.lower():
                    job_date = job.JobSubmitDateTime.Date
                    if (job_date.Year == today.year and 
                        job_date.Month == today.month and 
                        job_date.Day == today.day):
                        my_jobs_today.append(job)
            
            # SORTING
            active_jobs_all.sort(key=lambda x: x.JobSubmitDateTime, reverse=True)
            my_jobs_today.sort(key=lambda x: x.JobSubmitDateTime, reverse=True)

            # --- GENERATE HTML ---
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Farm Status</title>
                <meta http-equiv="refresh" content="10">
                <style>
                    body { font-family: 'Segoe UI', sans-serif; background: #1e1e1e; color: #ccc; padding: 20px; }
                    
                    /* Header & Button */
                    .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #444; padding-bottom: 15px; margin-bottom: 20px; }
                    h1 { margin: 0; color: #eee; font-size: 20px; }
                    .btn-refresh { background-color: #007acc; color: white; border: none; padding: 10px 20px; font-size: 14px; border-radius: 4px; cursor: pointer; font-weight: bold; }
                    .btn-refresh:hover { background-color: #005f9e; }
                    
                    /* Tables */
                    h2 { color: #eee; font-size: 16px; margin-top: 30px; border-left: 4px solid #555; padding-left: 10px; }
                    table { width: 100%; border-collapse: collapse; font-size: 14px; margin-bottom: 20px; background: #252526; }
                    th { text-align: left; background: #333; color: #aaa; padding: 10px; }
                    td { border-bottom: 1px solid #444; padding: 10px; vertical-align: middle; }
                    
                    /* Status Colors */
                    .st-Rendering, .st-Active { color: #8bc34a; font-weight: bold; }
                    .st-Queued { color: #d69d36; }
                    .st-Completed { color: #666; text-decoration: line-through; }
                    .st-Failed { color: #f44336; }
                    
                    /* Progress Bar */
                    .p-container { background: #444; width: 80px; height: 6px; border-radius: 4px; overflow: hidden; display: inline-block; margin-right: 10px; vertical-align: middle; }
                    .p-fill { height: 100%; background: #007acc; }
                    .st-Rendering .p-fill, .st-Active .p-fill { background: #8bc34a; }
                    .st-Queued .p-fill { background: #d69d36; }
                    
                    .empty { padding: 20px; text-align: center; color: #555; font-style: italic; }
                    .section-icon { margin-right: 8px; font-size: 1.2em; }
                    
                    /* Highlight My Rows */
                    .mine { background: #2d353b; }
                    .mine td { color: #fff; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>Deadline Monitor (Queue + ETA)</h1>
                    <div>
                        <span style="font-size:12px; color:#666; margin-right:15px">Updated: """ + timestamp + """</span>
                        <button class="btn-refresh" onclick="window.location.reload();">REFRESH</button>
                    </div>
                </div>

                <!-- GLOBAL ACTIVE -->
                <h2><span class="section-icon">&#128293;</span> Active Queue & Renders</h2>
                <table>
                    <thead><tr><th>User</th><th>Job Name</th><th>Status</th><th>Progress</th><th>ETA</th></tr></thead>
                    <tbody>
            """
            
            # --- GLOBAL TABLE ---
            if len(active_jobs_all) == 0:
                html += "<tr><td colspan='5' class='empty'>The farm is completely empty!</td></tr>"
            
            for job in active_jobs_all:
                percent = 0
                if job.JobTaskCount > 0:
                    percent = int((float(job.CompletedChunks) / float(job.JobTaskCount)) * 100)
                if percent > 100: percent = 100
                
                s_lower = job.JobStatus.lower()
                status_css = "Queued"
                if "rendering" in s_lower or "active" in s_lower: status_css = "Rendering"
                
                row_class = ""
                if job.JobUserName.lower() == MY_USERNAME.lower(): row_class = "mine"
                
                # GET ETA
                eta = get_eta_string(job)
                
                html += """
                <tr class='{}'>
                    <td style="font-weight:bold;">{}</td>
                    <td>{}</td>
                    <td class="st-{}">{}</td>
                    <td><div class='p-container'><div class='p-fill' style='width:{}%'></div></div>{}%</td>
                    <td>{}</td>
                </tr>""".format(row_class, job.JobUserName, job.JobName, status_css, job.JobStatus, percent, percent, eta)

            # --- MY JOBS TABLE ---
            html += """
                    </tbody>
                </table>

                <h2><span class="section-icon">&#128100;</span> My History (Today)</h2>
                <table>
                    <thead><tr><th>Job Name</th><th>Status</th><th>Progress</th><th>Time</th></tr></thead>
                    <tbody>
            """

            if len(my_jobs_today) == 0:
                html += "<tr><td colspan='4' class='empty'>No submissions today.</td></tr>"

            for job in my_jobs_today:
                percent = 0
                if job.JobTaskCount > 0:
                    percent = int((float(job.CompletedChunks) / float(job.JobTaskCount)) * 100)
                if percent > 100: percent = 100
                
                s_lower = job.JobStatus.lower()
                status_css = "Queued"
                if "rendering" in s_lower or "active" in s_lower: status_css = "Rendering"
                elif "completed" in s_lower: status_css = "Completed"
                elif "failed" in s_lower: status_css = "Failed"

                html += """
                <tr>
                    <td>{}</td>
                    <td class="st-{}">{}</td>
                    <td><div class='p-container'><div class='p-fill' style='width:{}%'></div></div>{}%</td>
                    <td>{}</td>
                </tr>""".format(job.JobName, status_css, job.JobStatus, percent, percent, job.JobSubmitDateTime.ToString("HH:mm"))

            html += """
                    </tbody>
                </table>
            </body>
            </html>
            """
            
            with open(output_file, "w") as f:
                f.write(html)
            
            if first_run:
                os.startfile(output_file)
                first_run = False
            
            time.sleep(REFRESH_SECONDS)

        except Exception as e:
            print( "Error: " + str(e) )
            time.sleep(REFRESH_SECONDS)