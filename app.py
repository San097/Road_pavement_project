"""
Root-level app entry point for Render deployment.
Imports the actual app from road_pavement_project.
"""
from road_pavement_project.app import app

if __name__ == "__main__":
    app.run()
