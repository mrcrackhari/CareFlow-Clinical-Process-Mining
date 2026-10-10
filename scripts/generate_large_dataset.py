import pandas as pd
import random
from datetime import datetime, timedelta
import os

# --- Configuration ---
NUM_PATIENTS = 450
START_DATE = datetime(2023, 10, 1, 8, 0, 0)
OUTPUT_FILE = 'data/raw/careflow_patient_events.csv'

# --- New Schema (aligned with team's schema.py) ---
COL_CASE_ID = "case_id"
COL_ACTIVITY = "activity"
COL_TIMESTAMP = "timestamp"
COL_RESOURCE = "resource"
COL_SHIFT = "shift"

ACT_REGISTRATION = "Registration"
ACT_TRIAGE = "Triage"
ACT_CONSULTATION = "Doctor Consultation"
ACT_XRAY = "X-Ray"
ACT_REVIEW = "Doctor Review"
ACT_DISCHARGE = "Discharge"
ACT_BLOOD_TEST = "Blood Test"  # Added based on your raw data

# Staff pools
DOCTORS = ["Dr. Smith", "Dr. Jones", "Dr. Patel", "Dr. Chen", "Dr. Garcia", 
           "Dr. Kim", "Dr. Brown", "Dr. Wilson", "Dr. Taylor", "Dr. Anderson"]
NURSES = ["Nurse Joy", "Nurse Ratched", "Nurse Jackie", "Nurse Chapel", 
          "Nurse Wilson", "Nurse Lee", "Nurse Davis"]
TECHNICIANS = ["Tech Miller", "Tech Garcia", "Tech Rodriguez"]

def get_shift(timestamp):
    """Determines the shift based on the hour of the day."""
    hour = timestamp.hour
    if 6 <= hour < 14:
        return "Morning"
    elif 14 <= hour < 22:
        return "Evening"
    else:
        return "Night"

def generate_patient_journey(case_id, start_time):
    events = []
    current_time = start_time
    
    def add_event(activity, resource):
        nonlocal current_time
        events.append({
            COL_CASE_ID: case_id,
            COL_ACTIVITY: activity,
            COL_TIMESTAMP: current_time,
            COL_RESOURCE: resource,
            COL_SHIFT: get_shift(current_time)
        })
        # Add a small delay after each event
        current_time += timedelta(minutes=random.randint(5, 15))
    
    # 1. Registration (Always first)
    add_event(ACT_REGISTRATION, random.choice(NURSES))
    current_time += timedelta(minutes=random.randint(5, 15))
    
    # 2. Triage (Always after registration)
    add_event(ACT_TRIAGE, random.choice(NURSES))
    current_time += timedelta(minutes=random.randint(10, 30))
    
    # 3. Middle Activities (Randomized to create "Spaghetti" paths)
    # Determine the type of journey
    journey_type = random.random()
    
    if journey_type < 0.30:
        # --- TYPE A: The Ideal Path (30% of patients) ---
        # Registration -> Triage -> Consultation -> X-Ray -> Review -> Discharge
        add_event(ACT_CONSULTATION, random.choice(DOCTORS))
        current_time += timedelta(minutes=random.randint(15, 45))
        add_event(ACT_XRAY, random.choice(TECHNICIANS))
        current_time += timedelta(minutes=random.randint(15, 30))
        add_event(ACT_REVIEW, random.choice(DOCTORS))
        current_time += timedelta(minutes=random.randint(10, 20))
        
    elif journey_type < 0.60:
        # --- TYPE B: Loop-Back (30% of patients) ---
        # Triage -> X-Ray -> Triage (The documented bottleneck)
        add_event(ACT_XRAY, random.choice(TECHNICIANS))
        current_time += timedelta(minutes=random.randint(15, 30))
        add_event(ACT_TRIAGE, random.choice(NURSES))  # LOOP BACK
        current_time += timedelta(minutes=random.randint(20, 40))
        add_event(ACT_CONSULTATION, random.choice(DOCTORS))
        current_time += timedelta(minutes=random.randint(15, 45))
        add_event(ACT_REVIEW, random.choice(DOCTORS))
        current_time += timedelta(minutes=random.randint(10, 20))
        
    elif journey_type < 0.80:
        # --- TYPE C: Double Test / Blood Test (20% of patients) ---
        # Triage -> Blood Test -> Blood Test -> Consultation
        add_event(ACT_BLOOD_TEST, random.choice(TECHNICIANS))
        current_time += timedelta(minutes=random.randint(15, 30))
        add_event(ACT_BLOOD_TEST, random.choice(TECHNICIANS))  # REPEAT
        current_time += timedelta(minutes=random.randint(20, 40))
        add_event(ACT_CONSULTATION, random.choice(DOCTORS))
        current_time += timedelta(minutes=random.randint(15, 45))
        add_event(ACT_REVIEW, random.choice(DOCTORS))
        current_time += timedelta(minutes=random.randint(10, 20))
        
    else:
        # --- TYPE D: Complex Journey (20% of patients) ---
        # Multiple tests + Loop-back (the "Spaghetti" journey)
        add_event(ACT_XRAY, random.choice(TECHNICIANS))
        current_time += timedelta(minutes=random.randint(15, 30))
        add_event(ACT_TRIAGE, random.choice(NURSES))  # LOOP BACK
        current_time += timedelta(minutes=random.randint(20, 40))
        add_event(ACT_BLOOD_TEST, random.choice(TECHNICIANS))
        current_time += timedelta(minutes=random.randint(15, 30))
        add_event(ACT_CONSULTATION, random.choice(DOCTORS))
        current_time += timedelta(minutes=random.randint(15, 45))
        add_event(ACT_REVIEW, random.choice(DOCTORS))
        current_time += timedelta(minutes=random.randint(10, 20))
    
    # 4. Discharge (Always last)
    add_event(ACT_DISCHARGE, random.choice(NURSES))
    
    return events

def main():
    all_events = []
    current_start_time = START_DATE
    
    print(f"Generating data for {NUM_PATIENTS} patients...")
    
    for i in range(1, NUM_PATIENTS + 1):
        case_id = f"CASE_{i:03d}"
        
        journey = generate_patient_journey(case_id, current_start_time)
        all_events.extend(journey)
        
        # Stagger patient arrivals (new patient every 5-15 mins)
        current_start_time += timedelta(minutes=random.randint(5, 15))
    
    # Convert to DataFrame
    df = pd.DataFrame(all_events)
    
    # Reorder columns to match schema
    df = df[[COL_CASE_ID, COL_ACTIVITY, COL_TIMESTAMP, COL_RESOURCE, COL_SHIFT]]
    
    # Format timestamp
    df[COL_TIMESTAMP] = df[COL_TIMESTAMP].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Sort by case_id and timestamp
    df = df.sort_values(by=[COL_CASE_ID, COL_TIMESTAMP]).reset_index(drop=True)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    # Save to CSV
    df.to_csv(OUTPUT_FILE, index=False)
    
    print(f"Success! Generated {len(df)} event rows for {NUM_PATIENTS} patients.")
    print(f"Saved to: {OUTPUT_FILE}")
    print(f"\nFirst 5 rows:")
    print(df.head())
    print(f"\nColumn names: {list(df.columns)}")
    print(f"\nUnique activities: {sorted(df[COL_ACTIVITY].unique())}")
    print(f"\nShift distribution:")
    print(df[COL_SHIFT].value_counts())

if __name__ == "__main__":
    main()