#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# برواز (Berwaz) - Auto-generate frames-data.js from folder structure
# ═══════════════════════════════════════════════════════════════════════════
#
# USAGE:
#   ./update-frames.sh
#
# FOLDER STRUCTURE:
#   content/
#   └── [Director Name]/
#       └── [optional: Project_Name Year/]
#           └── *.gif
#
# The script will:
# - Scan all GIF files in the content folder
# - Extract metadata from folder/file names
# - Generate frames-data.js automatically
# ═══════════════════════════════════════════════════════════════════════════

cd "$(dirname "$0")"

echo "═══════════════════════════════════════════════════════════════"
echo "  برواز (Berwaz) - Updating Frame Library"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Create temp file with all paths
find content -type f -name "*.gif" | sort > /tmp/giflist.txt
total=$(wc -l < /tmp/giflist.txt)

if [ "$total" -eq 0 ]; then
    echo "❌ No GIF files found in content/ folder"
    exit 1
fi

echo "📁 Found $total GIF files"
echo ""

# Start the JS file
echo "const FRAMES_DATA = [" > frames-data.js

id=1
while IFS= read -r filepath; do
    relpath="${filepath#content/}"
    director=$(echo "$relpath" | cut -d'/' -f1)
    filename=$(basename "$filepath")
    filename_noext="${filename%.*}"

    # Count path segments to determine structure
    segments=$(echo "$relpath" | tr '/' '\n' | wc -l)

    if [ "$segments" -eq 2 ]; then
        # File directly in director folder - extract info from filename
        source=$(echo "$filename_noext" | sed "s/_scene[0-9]*$//" | sed "s/ ([^)]*)//g" | sed "s/_/ /g" | sed "s/'/ /g" | cut -c1-40)
        year=$(echo "$filename" | grep -oE "'[0-9]{2}" | sed "s/'//g" | head -1)
        if [ -n "$year" ]; then year="20$year"; else year="2024"; fi
    else
        # File in project subfolder - extract from folder name
        project_folder=$(echo "$relpath" | cut -d'/' -f2)
        source=$(echo "$project_folder" | sed -E 's/_?[0-9]{4}//g' | sed 's/_/ /g' | cut -c1-40)
        year=$(echo "$project_folder" | grep -oE '[0-9]{4}' | tail -1)
        if [ -z "$year" ]; then year="2024"; fi
    fi

    # Extract scene number
    scene=$(echo "$filename_noext" | grep -oE 'scene[0-9]+' | sed 's/scene//')
    if [ -z "$scene" ]; then scene="1"; fi

    echo "    { id: \"$id\", title: \"مشهد $scene\", source: \"$source\", year: $year, director: \"$director\", dp: \"\", tags: [\"$year\", \"السعودية\"], mood: \"Cinematic\", lighting: \"Natural\", color: [\"#8B7355\", \"#D4A574\", \"#1A1A1A\"], aspect: \"16:9\", file: \"$relpath\" }," >> frames-data.js

    id=$((id + 1))
done < /tmp/giflist.txt

# Remove trailing comma and close array
sed -i '$ s/,$//' frames-data.js 2>/dev/null || sed -i '' '$ s/,$//' frames-data.js
echo "];" >> frames-data.js

# Cleanup
rm -f /tmp/giflist.txt

echo "✅ Generated frames-data.js with $((id - 1)) frames"
echo ""
echo "Directors found:"
grep -oP 'director: "[^"]*"' frames-data.js | sed 's/director: "//g' | sed 's/"//g' | sort -u | while read d; do
    count=$(grep -c "director: \"$d\"" frames-data.js)
    echo "   • $d ($count frames)"
done
echo ""
echo "═══════════════════════════════════════════════════════════════"
