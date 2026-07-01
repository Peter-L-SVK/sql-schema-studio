#!/bin/bash
# Build DEB package for SQL Schema Studio
set -e

VERSION=$(grep version pyproject.toml | head -1 | cut -d'"' -f2)
ARCH=all

echo "Building DEB for SQL Schema Studio v${VERSION}"

BUILD_DIR=deb_build
DEB_NAME=sql-schema-studio_${VERSION}_${ARCH}
rm -rf ${BUILD_DIR}
mkdir -p ${BUILD_DIR}/${DEB_NAME}/DEBIAN
mkdir -p ${BUILD_DIR}/${DEB_NAME}/usr/share/sql-schema-studio
mkdir -p ${BUILD_DIR}/${DEB_NAME}/usr/bin
mkdir -p ${BUILD_DIR}/${DEB_NAME}/usr/lib/python3/dist-packages

# Copy pyproject.toml for dependency management
cp pyproject.toml ${BUILD_DIR}/${DEB_NAME}/usr/share/sql-schema-studio/

# Copy Python source files as package
mkdir -p ${BUILD_DIR}/${DEB_NAME}/usr/lib/python3/dist-packages/src
cp -r src/* ${BUILD_DIR}/${DEB_NAME}/usr/lib/python3/dist-packages/src/

# Ensure __init__.py exists
if [ ! -f "${BUILD_DIR}/${DEB_NAME}/usr/lib/python3/dist-packages/src/__init__.py" ]; then
    touch ${BUILD_DIR}/${DEB_NAME}/usr/lib/python3/dist-packages/src/__init__.py
fi

# Remove __pycache__
find ${BUILD_DIR}/${DEB_NAME} -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Install icon
ICON_SRC="src/resources/ui/icons/logo.svg"
if [ -f "$ICON_SRC" ]; then
    mkdir -p ${BUILD_DIR}/${DEB_NAME}/usr/share/icons/hicolor/scalable/apps/
    cp $ICON_SRC ${BUILD_DIR}/${DEB_NAME}/usr/share/icons/hicolor/scalable/apps/sql-schema-studio.svg
else
    echo "Warning: Icon not found at $ICON_SRC"
    mkdir -p ${BUILD_DIR}/${DEB_NAME}/usr/share/icons/hicolor/scalable/apps/
    cat > ${BUILD_DIR}/${DEB_NAME}/usr/share/icons/hicolor/scalable/apps/sql-schema-studio.svg << 'SVG_EOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <rect width="100" height="100" rx="20" fill="#2d3748"/>
  <text x="50" y="55" font-family="Arial" font-size="40" font-weight="bold" fill="#48bb78" text-anchor="middle">SQL</text>
  <text x="50" y="75" font-family="Arial" font-size="12" fill="#a0aec0" text-anchor="middle">Schema Studio</text>
</svg>
SVG_EOF
fi

# Install desktop file
DESKTOP_SRC="src/resources/desktop/sql-schema-studio.desktop"
if [ -f "$DESKTOP_SRC" ]; then
    mkdir -p ${BUILD_DIR}/${DEB_NAME}/usr/share/applications/
    cp $DESKTOP_SRC ${BUILD_DIR}/${DEB_NAME}/usr/share/applications/
else
    mkdir -p ${BUILD_DIR}/${DEB_NAME}/usr/share/applications/
    cat > ${BUILD_DIR}/${DEB_NAME}/usr/share/applications/sql-schema-studio.desktop << 'EOF'
[Desktop Entry]
Name=SQL Schema Studio
Comment=Intelligent PostgreSQL Management Platform
Exec=/usr/bin/sql-schema-studio
Icon=sql-schema-studio
Terminal=false
Type=Application
Categories=Development;Database;IDE;
StartupWMClass=SQL Schema Studio
MimeType=text/x-sql;
EOF
fi

# Create launcher script with dependency checking
cat > ${BUILD_DIR}/${DEB_NAME}/usr/bin/sql-schema-studio << 'LAUNCHER'
#!/usr/bin/env python3
import sys
import os
import tomllib

# Add dist-packages to path
dist_packages = '/usr/lib/python3/dist-packages'
if os.path.exists(dist_packages):
    sys.path.insert(0, dist_packages)

def get_dependencies_from_pyproject():
    """Extract dependencies from pyproject.toml."""
    pyproject_path = '/usr/share/sql-schema-studio/pyproject.toml'
    if not os.path.exists(pyproject_path):
        return []
    
    with open(pyproject_path, 'rb') as f:
        data = tomllib.load(f)
    return data.get('project', {}).get('dependencies', [])

def get_import_name(package_name):
    """Map package names to their import names."""
    # Extract base package name without version specifiers
    base_name = package_name.split('>')[0].split('<')[0].split('=')[0].split('[')[0].strip()
    
    # Map package names to import names
    import_map = {
        'PyGObject': 'gi',
        'pycairo': 'cairo',
        'scikit-learn': 'sklearn',
        'psycopg': 'psycopg',
    }
    return import_map.get(base_name, base_name)

def check_packages():
    """Check for required packages and guide user on installation."""
    dependencies = get_dependencies_from_pyproject()
    if not dependencies:
        return
    
    missing = []
    for dep in dependencies:
        import_name = get_import_name(dep)
        try:
            __import__(import_name)
        except ImportError:
            missing.append(dep)
    
    if missing:
        print("\n" + "="*60)
        print("⚠ Missing Python packages detected!")
        print("="*60)
        print("\nThe following packages are required but not installed:")
        for pkg in missing:
            print(f"  • {pkg}")
        print("\nTo install them, run:")
        print("  sql-schema-studio-install-deps")
        print("\n" + "="*60 + "\n")
        sys.exit(1)

# Run the check
check_packages()

# Try to import and run main
try:
    from src.main import main
    sys.exit(main())
except ImportError as e:
    print(f"Error: Could not import SQL Schema Studio module: {e}", file=sys.stderr)
    print(f"Python path: {sys.path}", file=sys.stderr)
    sys.exit(1)
LAUNCHER
chmod +x ${BUILD_DIR}/${DEB_NAME}/usr/bin/sql-schema-studio

# Create dependency installer script
cat > ${BUILD_DIR}/${DEB_NAME}/usr/bin/sql-schema-studio-install-deps << 'INSTALL_DEPS'
#!/bin/bash
# SQL Schema Studio - Dependency Installer

echo "SQL Schema Studio - Python Dependency Installer"
echo "================================================"
echo ""

PYPROJECT="/usr/share/sql-schema-studio/pyproject.toml"

if [ ! -f "$PYPROJECT" ]; then
    echo "❌ pyproject.toml not found at: $PYPROJECT"
    exit 1
fi

echo "📋 Using dependencies from: $PYPROJECT"
echo ""

# Check for pip3
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 not found. Please install python3-pip:"
    echo "   sudo apt install python3-pip"
    exit 1
fi

# Check for pipx
HAS_PIPX=false
if command -v pipx &> /dev/null; then
    HAS_PIPX=true
fi

echo "Available installation methods:"
echo "  1) pipx (recommended - isolated environment)"
if [ "$HAS_PIPX" = true ]; then
    echo "     ✓ pipx is installed"
else
    echo "     ✗ pipx not installed (run: sudo apt install pipx && pipx ensurepath)"
fi
echo "  2) pip --user (user-only installation)"
echo "  3) pip with --break-system-packages (system-wide - Ubuntu 24.04+)"
echo ""
read -p "Choose method (1/2/3): " METHOD

case $METHOD in
    1)
        if [ "$HAS_PIPX" = false ]; then
            echo "Installing pipx..."
            sudo apt install -y pipx
            pipx ensurepath
            echo "Please restart your terminal or run: source ~/.bashrc"
        fi
        echo "Installing dependencies with pipx..."
        pipx install -r <(python3 -c "
import tomllib
with open('$PYPROJECT', 'rb') as f:
    data = tomllib.load(f)
deps = data.get('project', {}).get('dependencies', [])
for dep in deps:
    print(dep)
") --include-deps
        ;;
    2)
        echo "Installing dependencies with pip --user..."
        pip3 install --user -r <(python3 -c "
import tomllib
with open('$PYPROJECT', 'rb') as f:
    data = tomllib.load(f)
deps = data.get('project', {}).get('dependencies', [])
for dep in deps:
    print(dep)
")
        ;;
    3)
        echo "Installing dependencies system-wide (--break-system-packages)..."
        pip3 install -r <(python3 -c "
import tomllib
with open('$PYPROJECT', 'rb') as f:
    data = tomllib.load(f)
deps = data.get('project', {}).get('dependencies', [])
for dep in deps:
    print(dep)
") --break-system-packages
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "Dependencies installed successfully!"
echo "You can now run: sql-schema-studio"
INSTALL_DEPS
chmod +x ${BUILD_DIR}/${DEB_NAME}/usr/bin/sql-schema-studio-install-deps

# Create control file
cat > ${BUILD_DIR}/${DEB_NAME}/DEBIAN/control << EOF
Package: sql-schema-studio
Version: ${VERSION}
Section: database
Priority: optional
Architecture: ${ARCH}
Depends: python3 (>= 3.12),
         python3-psycopg2,
         python3-gi,
         python3-gi-cairo,
         python3-sqlparse,
         python3-keyring,
         python3-numpy,
         python3-matplotlib,
         python3-cairo,
         python3-paramiko,
         gir1.2-gtk-4.0,
         gir1.2-gtksource-5,
         gir1.2-vte-2.91
Recommends: pipx
Suggests: python3-faker, python3-sklearn, python3-kbcstorage
Maintainer: Peter Leukanič <peter@leukanic.eu>
Description: Intelligent PostgreSQL Management Platform
 SQL Schema Studio is a GTK4 desktop application for PostgreSQL database
 management with AI-powered analytics and extensible Python/Perl hooks.
 .
 Features:
  * Visual schema designer
  * SQL editor with syntax highlighting
  * AI-powered index advisor
  * Auto-vacuum recommendation engine
  * PostgreSQL log analyzer
  * Extensible Python/Perl hook system
  * SSH tunnel support
  * Keboola integration for data normalization
 .
 ⚠  Some Python dependencies must be installed separately.
 Run 'sql-schema-studio-install-deps' after installation.
License: GPL-3.0-or-later
Homepage: https://github.com/peter-leukanic/sql-schema-studio
EOF

# Create post-installation script
cat > ${BUILD_DIR}/${DEB_NAME}/DEBIAN/postinst << 'POSTINST'
#!/bin/bash
set -e

echo ""
echo "┌─────────────────────────────────────────────────────────┐"
echo "│         SQL Schema Studio installed!                │"
echo "└─────────────────────────────────────────────────────────┘"
echo ""
echo "Version: ${VERSION}"
echo ""
echo "⚠  Some Python dependencies must be installed separately."
echo ""
echo "To install them, run:"
echo "   sql-schema-studio-install-deps"
echo ""
echo " To start the application:"
echo "   sql-schema-studio"
echo ""
echo " For more information:"
echo "   https://github.com/peter-leukanic/sql-schema-studio"
echo ""
POSTINST
chmod +x ${BUILD_DIR}/${DEB_NAME}/DEBIAN/postinst

# Build the package
dpkg-deb --build ${BUILD_DIR}/${DEB_NAME}

# Move to current directory
mv ${BUILD_DIR}/${DEB_NAME}.deb .

echo ""
echo "✅ DEB built: ${DEB_NAME}.deb"
echo ""
echo "Install with:"
echo "   sudo dpkg -i ${DEB_NAME}.deb"
echo ""
echo "If dependencies fail:"
echo "   sudo apt --fix-broken install"
echo ""
echo "After installation, install Python dependencies:"
echo "   sql-schema-studio-install-deps"
echo ""
echo "Run the app:"
echo "   sql-schema-studio"
