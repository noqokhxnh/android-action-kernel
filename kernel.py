import os
import time
import subprocess
import json
from typing import Dict, Any, List  # Thêm List vào đây
from dotenv import load_dotenv

import google.generativeai as genai
import sanitizer

# --- CONFIGURATION ---
load_dotenv()
ADB_PATH = "adb"  
MODEL_NAME = "gemini-2.5-flash"  
SCREEN_DUMP_PATH = "/sdcard/window_dump.xml"
LOCAL_DUMP_PATH = "window_dump.xml"


# Cấu hình API Key
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel(MODEL_NAME)

def run_adb_command(command: List[str]):
    """Executes a shell command via ADB."""
    result = subprocess.run([ADB_PATH] + command, capture_output=True, text=True)
    if result.stderr and "error" in result.stderr.lower():
        print(f"❌ ADB Error: {result.stderr.strip()}")
    return result.stdout.strip()

def get_screen_state() -> str:
    """Dumps the current UI XML and returns the sanitized JSON string."""
    run_adb_command(["shell", "uiautomator", "dump", SCREEN_DUMP_PATH])
    run_adb_command(["pull", SCREEN_DUMP_PATH, LOCAL_DUMP_PATH])
    
    if not os.path.exists(LOCAL_DUMP_PATH):
        return "Error: Could not capture screen."
        
    with open(LOCAL_DUMP_PATH, "r", encoding="utf-8") as f:
        xml_content = f.read()
        
    elements = sanitizer.get_interactive_elements(xml_content)
    return json.dumps(elements, indent=2)

def execute_action(action: Dict[str, Any]):
    """Executes the action decided by the LLM."""
    act_type = action.get("action")
    
    if act_type == "tap":
        coords = action.get("coordinates")
        if coords:
            x, y = coords
            print(f"👉 Tapping: ({x}, {y})")
            run_adb_command(["shell", "input", "tap", str(x), str(y)])
        
    elif act_type == "type":
        text = action.get("text", "").replace(" ", "%s")
        print(f"⌨️ Typing: {action.get('text')}")
        run_adb_command(["shell", "input", "text", text])
        
    elif act_type == "home":
        print("🏠 Going Home")
        run_adb_command(["shell", "input", "keyevent", "3"]) # Mã 3 là Home
        
    elif act_type == "back":
        print("🔙 Going Back")
        run_adb_command(["shell", "input", "keyevent", "4"]) # Mã 4 là Back
        
    elif act_type == "wait":
        print("⏳ Waiting...")
        time.sleep(2)
        
    elif act_type == "done":
        print("✅ Goal Achieved.")
        exit(0)

def get_llm_decision(goal: str, screen_context: str) -> Dict[str, Any]:
    """Sends screen context to Gemini and asks for the next move."""
    prompt = f"""
    You are an Android Driver Agent. Output ONLY a valid JSON object.
    
    GOAL: {goal}
    SCREEN_CONTEXT:
    {screen_context}

    Available Actions:
    - {{"action": "tap", "coordinates": [x, y], "reason": "..."}}
    - {{"action": "type", "text": "...", "reason": "..."}}
    - {{"action": "home", "reason": "..."}}
    - {{"action": "back", "reason": "..."}}
    - {{"action": "wait", "reason": "..."}}
    - {{"action": "done", "reason": "..."}}
    """
    
    # Cú pháp chuẩn của Gemini SDK
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    
    return json.loads(response.text)

def run_agent(goal: str, max_steps=10):
    print(f"🚀 Android Use Agent Started. Goal: {goal}")
    for step in range(max_steps):
        print(f"\n--- Step {step + 1} ---")
        print("👀 Scanning Screen...")
        screen_context = get_screen_state()
        
        print("🧠 Thinking...")
        try:
            decision = get_llm_decision(goal, screen_context)
            print(f"💡 Decision: {decision.get('reason')}")
            execute_action(decision)
        except Exception as e:
            print(f"❌ Error during decision/action: {e}")
        
        time.sleep(2)

if __name__ == "__main__":
    GOAL = input("Enter your goal: ")
    run_agent(GOAL)