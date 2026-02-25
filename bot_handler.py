#!/usr/bin/env python3
"""
Telegram Bot Command Handler für EMEA Sales Alerts
Wird von OpenClaw aufgerufen wenn Commands empfangen werden
"""

import sys
import os

# Add leadtracker directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alert_service import cmd_next, cmd_hot, cmd_stale

def handle_command(command_text: str) -> str:
    """
    Verarbeitet Telegram Commands und gibt Antwort zurück
    
    Commands:
    /next - Zeigt wichtigste offene Task
    /hot - Top 5 Opportunities nach MEDDPICC
    /stale - Deals die schlummern (>7 Tage)
    /help - Hilfe anzeigen
    """
    command = command_text.strip().lower()
    
    if command == "/next":
        message, _ = cmd_next()
        return message
    
    elif command == "/hot":
        message, _ = cmd_hot()
        return message
    
    elif command == "/stale":
        message, _ = cmd_stale()
        return message
    
    elif command in ["/help", "/start", "help"]:
        return """🎯 *EMEA Sales Alert System*

Verfügbare Commands:
/next - Wichtigste nächste Aktivität
/hot - Top 5 Opportunities (MEDDPICC)
/stale - Schlummernde Deals (>7 Tage)
/help - Diese Hilfe

Dashboard: https://pipo-bitwise-lead-tracker.streamlit.app
"""
    
    else:
        return None  # Nicht behandelter Command


if __name__ == "__main__":
    # Wird von OpenClaw aufgerufen mit Command als Argument
    if len(sys.argv) > 1:
        command = sys.argv[1]
        response = handle_command(command)
        if response:
            print(response)
        else:
            print("Unbekannter Command. Tippe /help für Hilfe.")
    else:
        print("Kein Command angegeben.")
