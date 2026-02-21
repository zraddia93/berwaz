#!/usr/bin/env python3
"""
Berwaz Admin Tool
=================
A simple command-line tool to manage frames in your Berwaz website.

Features:
- List all frames
- Add new frames (with optional AI tagging)
- Delete frames
- Sync with R2 storage

Usage:
    python3 berwaz-admin.py

Requirements:
    pip3 install boto3 pillow --break-system-packages
"""

import os
import sys
import json
import re
import subprocess
from pathlib import Path

# Configuration
FRAMES_DATA_FILE = "frames-data.js"
CONTENT_DIR = "content"
R2_BUCKET = "berwaz"
R2_ENDPOINT = "https://4b1db6e690fcbe9af2ffffd6accc93f6.r2.cloudflarestorage.com"
R2_PUBLIC_URL = "https://pub-b8befece66bc4203bab663b2ed292cd4.r2.dev"

# Directors list
DIRECTORS = [
    "Abdullah Algallaf",
    "Abdullah Alkhamees",
    "Abdullah Majed",
    "Abdulrahman Elsingergy",
    "Ali Alkalthami",
    "Bader Nour",
    "Fahad Alammari",
    "Faisal Alobrah",
    "Majed Aleissa",
    "Malek Alhammami",
    "Meshal Aljasser",
    "Mishary Almazyad",
    "Mohammad Alhamdan",
    "Mohammad Alharthi",
    "Mohammad Almulla",
    "Mohammad Alsuliman"
]

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')

def print_header():
    print("\n" + "=" * 50)
    print("       🎬 BERWAZ ADMIN TOOL 🎬")
    print("=" * 50)

def print_menu():
    print("\nWhat would you like to do?\n")
    print("  1. 📋 List all frames")
    print("  2. 🔍 Search frames")
    print("  3. ➕ Add new frame")
    print("  4. 🗑️  Delete frame")
    print("  5. 📊 Show statistics")
    print("  6. ☁️  Sync with R2")
    print("  7. 💾 Push changes to GitHub")
    print("  8. ❌ Exit")
    print()

def load_frames_data():
    """Load frames from frames-data.js"""
    try:
        with open(FRAMES_DATA_FILE, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract the array from the JS file
        match = re.search(r'const FRAMES_DATA = (\[[\s\S]*\]);', content)
        if match:
            json_str = match.group(1)
            # Fix trailing commas for JSON parsing
            json_str = re.sub(r',(\s*[\]}])', r'\1', json_str)
            return json.loads(json_str)
        return []
    except Exception as e:
        print(f"Error loading frames: {e}")
        return []

def save_frames_data(frames):
    """Save frames to frames-data.js"""
    try:
        # Format frames as JavaScript
        js_content = "const FRAMES_DATA = [\n"
        for i, frame in enumerate(frames):
            js_content += "    " + json.dumps(frame, ensure_ascii=False)
            if i < len(frames) - 1:
                js_content += ","
            js_content += "\n"
        js_content += "];\n"

        with open(FRAMES_DATA_FILE, 'w', encoding='utf-8') as f:
            f.write(js_content)

        print("✅ Frames data saved successfully!")
        return True
    except Exception as e:
        print(f"❌ Error saving frames: {e}")
        return False

def list_frames(frames, limit=20):
    """List all frames"""
    print(f"\n📋 Total frames: {len(frames)}\n")

    if not frames:
        print("No frames found.")
        return

    # Group by director
    by_director = {}
    for frame in frames:
        director = frame.get('director', 'Unknown')
        if director not in by_director:
            by_director[director] = []
        by_director[director].append(frame)

    for director, director_frames in by_director.items():
        print(f"\n👤 {director}: {len(director_frames)} frames")

    print(f"\n" + "-" * 40)
    show_all = input(f"Show all {len(frames)} frames? (y/n): ").lower() == 'y'

    if show_all:
        for i, frame in enumerate(frames):
            print(f"  [{frame['id']}] {frame.get('source', 'Unknown')} - {frame.get('director', 'Unknown')}")
            if (i + 1) % 50 == 0:
                cont = input("\n--- Press Enter to continue (or 'q' to stop) ---")
                if cont.lower() == 'q':
                    break

def search_frames(frames):
    """Search frames by various criteria"""
    print("\n🔍 Search Frames")
    print("-" * 30)
    query = input("Enter search term (title, director, tag, source): ").lower()

    if not query:
        print("No search term provided.")
        return

    results = []
    for frame in frames:
        searchable = f"{frame.get('title', '')} {frame.get('director', '')} {frame.get('source', '')} {' '.join(frame.get('tags', []))}".lower()
        if query in searchable:
            results.append(frame)

    print(f"\n📊 Found {len(results)} matching frames:\n")
    for frame in results[:30]:
        print(f"  [{frame['id']}] {frame.get('source', 'Unknown')} - {frame.get('director', 'Unknown')}")
        print(f"       Tags: {', '.join(frame.get('tags', [])[:5])}")

    if len(results) > 30:
        print(f"\n  ... and {len(results) - 30} more")

def add_frame(frames):
    """Add a new frame"""
    print("\n➕ Add New Frame")
    print("-" * 30)

    # Select director
    print("\nSelect director:")
    for i, director in enumerate(DIRECTORS, 1):
        print(f"  {i}. {director}")

    try:
        dir_choice = int(input("\nEnter number: ")) - 1
        if dir_choice < 0 or dir_choice >= len(DIRECTORS):
            print("Invalid choice.")
            return frames
        director = DIRECTORS[dir_choice]
    except ValueError:
        print("Invalid input.")
        return frames

    # Get frame details
    source = input("Source/Project name: ")
    year = input("Year (e.g., 2023): ")

    # Get file path
    print(f"\nGIF file should be in: content/{director}/[project_folder]/")
    file_path = input("Enter relative file path (e.g., Project_Name/scene1.gif): ")

    full_file_path = f"{director}/{file_path}"

    # Generate tags
    print("\nEnter tags (comma-separated):")
    print("Example: desert, sunset, silhouette, wide shot, warm tones")
    tags_input = input("Tags: ")
    tags = [t.strip() for t in tags_input.split(',') if t.strip()]

    # Get mood and lighting
    mood = input("Mood (e.g., Cinematic, Dramatic, Peaceful): ") or "Cinematic"
    lighting = input("Lighting (e.g., Natural, Golden Hour, Low-Key): ") or "Natural"

    # Generate new ID
    max_id = max([int(f['id']) for f in frames] + [0])
    new_id = str(max_id + 1)

    # Create new frame entry
    new_frame = {
        "id": new_id,
        "title": f"مشهد {new_id}",
        "source": source,
        "year": int(year) if year.isdigit() else 2024,
        "director": director,
        "dp": "",
        "tags": tags,
        "mood": mood,
        "lighting": lighting,
        "color": ["#8B7355", "#D4A574", "#1A1A1A"],
        "aspect": "2.20:1",
        "file": full_file_path
    }

    print("\n📝 New frame preview:")
    print(json.dumps(new_frame, indent=2, ensure_ascii=False))

    confirm = input("\nAdd this frame? (y/n): ").lower()
    if confirm == 'y':
        frames.append(new_frame)
        print(f"✅ Frame {new_id} added!")
        print("\n⚠️  Remember to:")
        print(f"   1. Upload the GIF to R2: content/{full_file_path}")
        print("   2. Run 'Push changes to GitHub' from the menu")

    return frames

def delete_frame(frames):
    """Delete a frame"""
    print("\n🗑️  Delete Frame")
    print("-" * 30)

    frame_id = input("Enter frame ID to delete: ")

    frame_to_delete = None
    for frame in frames:
        if frame['id'] == frame_id:
            frame_to_delete = frame
            break

    if not frame_to_delete:
        print(f"❌ Frame {frame_id} not found.")
        return frames

    print(f"\n📝 Frame to delete:")
    print(f"   ID: {frame_to_delete['id']}")
    print(f"   Source: {frame_to_delete.get('source', 'Unknown')}")
    print(f"   Director: {frame_to_delete.get('director', 'Unknown')}")
    print(f"   File: {frame_to_delete.get('file', 'Unknown')}")

    confirm = input("\n⚠️  Are you sure you want to delete this frame? (yes/no): ")
    if confirm.lower() == 'yes':
        frames = [f for f in frames if f['id'] != frame_id]
        print(f"✅ Frame {frame_id} deleted!")
        print("\n⚠️  Remember to:")
        print(f"   1. Delete the GIF from R2: content/{frame_to_delete.get('file', '')}")
        print("   2. Run 'Push changes to GitHub' from the menu")
    else:
        print("Deletion cancelled.")

    return frames

def show_statistics(frames):
    """Show frame statistics"""
    print("\n📊 Frame Statistics")
    print("=" * 40)

    print(f"\n📈 Total frames: {len(frames)}")

    # By director
    print("\n👤 By Director:")
    by_director = {}
    for frame in frames:
        director = frame.get('director', 'Unknown')
        by_director[director] = by_director.get(director, 0) + 1

    for director, count in sorted(by_director.items(), key=lambda x: -x[1]):
        bar = "█" * (count // 10)
        print(f"   {director}: {count} {bar}")

    # By year
    print("\n📅 By Year:")
    by_year = {}
    for frame in frames:
        year = frame.get('year', 'Unknown')
        by_year[year] = by_year.get(year, 0) + 1

    for year, count in sorted(by_year.items()):
        print(f"   {year}: {count}")

    # Top tags
    print("\n🏷️  Top Tags:")
    all_tags = {}
    for frame in frames:
        for tag in frame.get('tags', []):
            all_tags[tag] = all_tags.get(tag, 0) + 1

    top_tags = sorted(all_tags.items(), key=lambda x: -x[1])[:10]
    for tag, count in top_tags:
        print(f"   {tag}: {count}")

def sync_r2():
    """Sync content with R2"""
    print("\n☁️  Sync with R2")
    print("-" * 30)
    print("\nThis will sync your local content folder with R2.")
    print("Make sure rclone is configured.\n")

    choice = input("1. Upload new files to R2\n2. List R2 contents\n3. Cancel\n\nChoice: ")

    if choice == '1':
        print("\nUploading to R2...")
        result = subprocess.run(
            ['rclone', 'copy', './content', 'r2:berwaz/content', '--progress', '--transfers', '10'],
            capture_output=False
        )
        if result.returncode == 0:
            print("✅ Upload complete!")
        else:
            print("❌ Upload failed. Make sure rclone is configured.")

    elif choice == '2':
        print("\nListing R2 contents...")
        result = subprocess.run(
            ['rclone', 'ls', 'r2:berwaz/content', '--max-depth', '2'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(result.stdout[:2000])
            if len(result.stdout) > 2000:
                print("... (truncated)")
        else:
            print("❌ Could not list R2. Make sure rclone is configured.")

def push_to_github():
    """Push changes to GitHub"""
    print("\n💾 Push Changes to GitHub")
    print("-" * 30)

    # Check for changes
    result = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True)
    if not result.stdout.strip():
        print("No changes to push.")
        return

    print("\nChanged files:")
    print(result.stdout)

    confirm = input("\nCommit and push these changes? (y/n): ").lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    message = input("Commit message (or press Enter for default): ")
    if not message:
        message = "Update frames data"

    # Git commands
    print("\n📤 Pushing to GitHub...")

    subprocess.run(['git', 'add', 'frames-data.js'])
    subprocess.run(['git', 'commit', '-m', message])
    result = subprocess.run(['git', 'push'], capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ Changes pushed to GitHub!")
        print("🌐 Your site will update in 1-2 minutes.")
        print(f"   https://zraddia93.github.io/berwaz/")
    else:
        print("❌ Push failed. You may need to authenticate.")
        print(result.stderr)

def main():
    """Main function"""
    clear_screen()
    print_header()

    # Load frames data
    frames = load_frames_data()
    print(f"\n✅ Loaded {len(frames)} frames")

    while True:
        print_menu()
        choice = input("Enter choice (1-8): ").strip()

        if choice == '1':
            list_frames(frames)
        elif choice == '2':
            search_frames(frames)
        elif choice == '3':
            frames = add_frame(frames)
            save_frames_data(frames)
        elif choice == '4':
            frames = delete_frame(frames)
            save_frames_data(frames)
        elif choice == '5':
            show_statistics(frames)
        elif choice == '6':
            sync_r2()
        elif choice == '7':
            push_to_github()
        elif choice == '8':
            print("\n👋 Goodbye!\n")
            break
        else:
            print("Invalid choice. Please try again.")

        input("\n--- Press Enter to continue ---")
        clear_screen()
        print_header()

if __name__ == "__main__":
    main()
