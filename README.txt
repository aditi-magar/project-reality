PROJECT REALITY — STARTER WEBSITE

WHAT THIS IS
A first working version of the Project Reality dashboard, built with Python and Streamlit using the CSV supplied with this project.

IMPORTANT DATA NOTE
The CSV is aggregated by physical-progress category, not a list of individual projects. The website therefore shows summary charts only. It does not claim to identify specific project or contractor wrongdoing. Confirm the CSV's figures and source against the official dashboard before treating them as verified findings.

FILES
- app.py: main website code
- requirements.txt: Python packages required
- data/Project_Reality_PAIMANA_Progress_Summary.csv: data file used by the dashboard

HOW TO RUN ON WINDOWS
1. Install Python 3.10 or later from https://www.python.org/downloads/ if it is not already installed.
2. Extract this ZIP file to a folder.
3. Open Command Prompt or a terminal inside the extracted Project_Reality_Starter folder.
4. Run these commands, one at a time:

   py -m venv .venv
   .venv\Scripts\activate
   py -m pip install -r requirements.txt
   streamlit run app.py

5. A browser tab should open with the website. If it does not, copy the Local URL shown in the terminal (usually http://localhost:8501) into your browser.

HOW TO STOP
Click the terminal and press Ctrl+C.

NEXT PROJECT STEP
Once the dashboard runs, decide whether to replace/extend the aggregated data with individual project records. This is necessary before building true project-level evidence pages or risk flags.
