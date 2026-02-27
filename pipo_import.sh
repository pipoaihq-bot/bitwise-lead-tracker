#!/bin/bash
# Pipo CSV/XLSX Import Wrapper
# Handles DB copy to local tmp, import, copy back
# Usage: ./pipo_import.sh <file_or_directory> [source_tag]
#
# Examples:
#   ./pipo_import.sh ~/Downloads/apollo_export.csv "Apollo"
#   ./pipo_import.sh ~/Downloads/ "LinkedIn"

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_MAC="$SCRIPT_DIR/bitwise_leads.db"
DB_TMP="/tmp/pipo_leads_import.db"
IMPORTER="$SCRIPT_DIR/csv_importer.py"

INPUT="${1:-}"
SOURCE_TAG="${2:-Manual}"

if [ -z "$INPUT" ]; then
    echo "Usage: $0 <file_or_directory> [source_tag]"
    echo ""
    echo "Beispiele:"
    echo "  $0 ~/Downloads/apollo_export.csv 'Apollo'"
    echo "  $0 ~/Downloads/ 'LinkedIn'"
    exit 1
fi

echo ""
echo "=================================================="
echo "🚀 Pipo CSV Import Pipeline"
echo "   Input:  $INPUT"
echo "   Source: $SOURCE_TAG"
echo "   DB:     $DB_MAC"
echo "=================================================="

# 1. Copy DB to local tmp (avoids FUSE/network issues)
echo ""
echo "📦 Kopiere DB lokal..."
cp "$DB_MAC" "$DB_TMP"
BEFORE=$(python3 -c "import sqlite3; print(sqlite3.connect('$DB_TMP').execute('SELECT COUNT(*) FROM leads').fetchone()[0])")
echo "   Vorher: $BEFORE Leads"

# 2. Run import
echo ""
echo "📥 Importiere..."
if [ -d "$INPUT" ]; then
    python3 "$IMPORTER" "$INPUT" --source "$SOURCE_TAG" --db "$DB_TMP"
else
    python3 "$IMPORTER" "$INPUT" --source "$SOURCE_TAG" --db "$DB_TMP"
fi

# 3. Copy back
AFTER=$(python3 -c "import sqlite3; print(sqlite3.connect('$DB_TMP').execute('SELECT COUNT(*) FROM leads').fetchone()[0])")
NEW=$((AFTER - BEFORE))

echo ""
echo "💾 Speichere zurück..."
cp "$DB_TMP" "$DB_MAC"
rm -f "$DB_TMP"

echo ""
echo "=================================================="
echo "✅ FERTIG!"
echo "   Vorher:   $BEFORE Leads"
echo "   Nachher:  $AFTER Leads"
echo "   Neu:      +$NEW Leads"
echo "=================================================="
