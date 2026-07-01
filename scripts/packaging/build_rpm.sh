#!/bin/bash
# =============================================================================
# SQL Schema Studio - RPM Package Build Script
# =============================================================================
# This script builds an RPM package for SQL Schema Studio.
# It creates a source tarball, generates a spec file, and builds the RPM.
#
# Usage: ./scripts/packaging/build_rpm.sh
#
# The script automatically detects the project root, version from pyproject.toml,
# and handles the build process with --nodeps to bypass dependency checks
# (required for Ubuntu-based CI runners).
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# 1. Locate project root directory (where pyproject.toml is located)
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in scripts/packaging/build_rpm.sh, so go up 2 levels
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "Building RPM for SQL Schema Studio from $PROJECT_ROOT"

# -----------------------------------------------------------------------------
# 2. Validate pyproject.toml exists
# -----------------------------------------------------------------------------
if [ ! -f "pyproject.toml" ]; then
    echo "ERROR: pyproject.toml not found in $PROJECT_ROOT"
    echo "Current directory: $(pwd)"
    echo "Files: $(ls -la)"
    exit 1
fi

# -----------------------------------------------------------------------------
# 3. Extract version from pyproject.toml
# -----------------------------------------------------------------------------
VERSION=$(grep "^version" pyproject.toml | head -1 | cut -d'"' -f2)
if [ -z "$VERSION" ]; then
    echo "ERROR: Could not find version in pyproject.toml"
    exit 1
fi

RELEASE=1
ARCH=noarch

echo "Version: $VERSION"

# -----------------------------------------------------------------------------
# 4. Setup RPM build environment
# -----------------------------------------------------------------------------
BUILD_DIR=~/rpmbuild
mkdir -p ${BUILD_DIR}/{BUILD,RPMS,SOURCES,SPECS,SRPMS,BUILDROOT}

# -----------------------------------------------------------------------------
# 5. Create source tarball
# -----------------------------------------------------------------------------
echo "Creating source tarball..."
tar --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' \
    -czf ${BUILD_DIR}/SOURCES/sql-schema-studio-${VERSION}.tar.gz \
    --transform "s/^/sql-schema-studio-${VERSION}\//" \
    src/ pyproject.toml README.md LICENSE 2>/dev/null || true

if [ ! -f "${BUILD_DIR}/SOURCES/sql-schema-studio-${VERSION}.tar.gz" ]; then
    echo "ERROR: Failed to create source tarball"
    exit 1
fi

# -----------------------------------------------------------------------------
# 6. Generate changelog date (RFC format for RPM)
# -----------------------------------------------------------------------------
CHANGELOG_DATE=$(LC_TIME=C date +"%a %b %d %Y")

# -----------------------------------------------------------------------------
# 7. Create RPM spec file
# -----------------------------------------------------------------------------
cat > ${BUILD_DIR}/SPECS/sql-schema-studio.spec << 'SPEC_EOF'
Name:           sql-schema-studio
Version:        VERSION_PLACEHOLDER
Release:        1%{?dist}
Summary:        Intelligent PostgreSQL Management Platform with AI analytics

License:        GPL-3.0-or-later
URL:            https://github.com/peter-leukanic/sql-schema-studio
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  python3-devel

# System-level dependencies (available as RPMs)
Requires:       python3 >= 3.12
Requires:       gtk4
Requires:       gtksourceview5
Requires:       vte291-gtk4

# Python packages available as RPMs (optional - some may not be available)
# These are here for convenience but not strictly required
# since the launcher will handle missing Python packages
Requires:       python3-psycopg2
Requires:       python3-gobject
Requires:       python3-sqlparse
Requires:       python3-keyring
Requires:       python3-numpy
Requires:       python3-matplotlib
Requires:       python3-cairo
Requires:       python3-paramiko
Requires:       python3-scikit-learn

%description
SQL Schema Studio is a GTK4 desktop application for PostgreSQL database
management with AI-powered analytics and extensible Python/Perl hooks.

Features:
- Visual schema designer with drag-and-drop
- SQL editor with syntax highlighting
- AI-powered index advisor
- Auto-vacuum recommendation engine
- PostgreSQL log analyzer
- Extensible Python/Perl hook system
- SSH tunnel support
- Keboola integration for data normalization

%prep
%setup -q

%install
# Create Python package directory - use absolute path
mkdir -p %{buildroot}/usr/lib/python3/dist-packages/src
cp -r src/* %{buildroot}/usr/lib/python3/dist-packages/src/

# Ensure __init__.py exists
if [ ! -f "%{buildroot}/usr/lib/python3/dist-packages/src/__init__.py" ]; then
    touch %{buildroot}/usr/lib/python3/dist-packages/src/__init__.py
fi

# Remove __pycache__
find %{buildroot} -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Copy pyproject.toml for dependency management
mkdir -p %{buildroot}/usr/share/sql-schema-studio/
cp pyproject.toml %{buildroot}/usr/share/sql-schema-studio/

# Install icon
mkdir -p %{buildroot}/usr/share/icons/hicolor/scalable/apps/
if [ -f "src/resources/ui/icons/logo.svg" ]; then
    cp src/resources/ui/icons/logo.svg %{buildroot}/usr/share/icons/hicolor/scalable/apps/sql-schema-studio.svg
elif [ -f "src/resources/ui/icons/sql-schema-studio.svg" ]; then
    cp src/resources/ui/icons/sql-schema-studio.svg %{buildroot}/usr/share/icons/hicolor/scalable/apps/sql-schema-studio.svg
else
    cat > %{buildroot}/usr/share/icons/hicolor/scalable/apps/sql-schema-studio.svg << 'SVG_EOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <rect width="100" height="100" rx="20" fill="#2d3748"/>
  <text x="50" y="55" font-family="Arial" font-size="40" font-weight="bold" fill="#48bb78" text-anchor="middle">SQL</text>
  <text x="50" y="75" font-family="Arial" font-size="12" fill="#a0aec0" text-anchor="middle">Schema Studio</text>
</svg>
SVG_EOF
fi

# Install desktop file
mkdir -p %{buildroot}/usr/share/applications/
if [ -f "src/resources/desktop/sql-schema-studio.desktop" ]; then
    cp src/resources/desktop/sql-schema-studio.desktop %{buildroot}/usr/share/applications/
else
    cat > %{buildroot}/usr/share/applications/sql-schema-studio.desktop << 'DESKTOP_EOF'
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
Keywords=postgresql;database;sql;schema;designer;analytics;
DESKTOP_EOF
fi

# Create launcher script with dependency checking
mkdir -p %{buildroot}/usr/bin
cat > %{buildroot}/usr/bin/sql-schema-studio << 'LAUNCHER_EOF'
#!/usr/bin/env python3
import sys
import os
import tomllib

# Add the dist-packages directory to sys.path
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
        print("⚠️  Missing Python packages detected!")
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
    print(f"Error: Could not import SQL Schema Studio module", file=sys.stderr)
    print(f"Details: {e}", file=sys.stderr)
    print(f"Python path: {sys.path}", file=sys.stderr)
    sys.exit(1)
LAUNCHER_EOF
chmod 755 %{buildroot}/usr/bin/sql-schema-studio

# Create dependency installer script
cat > %{buildroot}/usr/bin/sql-schema-studio-install-deps << 'INSTALL_EOF'
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
    echo "   sudo dnf install python3-pip"
    exit 1
fi

echo "Available installation methods:"
echo "  1) pip --user (user-only installation - recommended)"
echo "  2) sudo pip (system-wide installation)"
echo ""
read -p "Choose method (1/2): " METHOD

case $METHOD in
    1)
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
    2)
        echo "Installing dependencies system-wide..."
        sudo pip3 install -r <(python3 -c "
import tomllib
with open('$PYPROJECT', 'rb') as f:
    data = tomllib.load(f)
deps = data.get('project', {}).get('dependencies', [])
for dep in deps:
    print(dep)
")
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "✅ Dependencies installed successfully!"
echo "You can now run: sql-schema-studio"
INSTALL_EOF
chmod 755 %{buildroot}/usr/bin/sql-schema-studio-install-deps

%files
/usr/lib/python3/dist-packages/src/
/usr/bin/sql-schema-studio
/usr/bin/sql-schema-studio-install-deps
/usr/share/icons/hicolor/scalable/apps/sql-schema-studio.svg
/usr/share/applications/sql-schema-studio.desktop
/usr/share/sql-schema-studio/pyproject.toml
%doc README.md LICENSE

%changelog
* CHANGELOG_DATE_PLACEHOLDER Peter Leukanič <peter@leukanic.eu> - VERSION_PLACEHOLDER-1
- Release vVERSION_PLACEHOLDER
SPEC_EOF

# -----------------------------------------------------------------------------
# 8. Replace placeholders in spec file
# -----------------------------------------------------------------------------
sed -i "s/VERSION_PLACEHOLDER/${VERSION}/g" ${BUILD_DIR}/SPECS/sql-schema-studio.spec
sed -i "s/CHANGELOG_DATE_PLACEHOLDER/${CHANGELOG_DATE}/g" ${BUILD_DIR}/SPECS/sql-schema-studio.spec

# -----------------------------------------------------------------------------
# 9. Build the RPM package
# -----------------------------------------------------------------------------
echo "Building RPM..."

# --nodeps bypasses dependency checks (required on Ubuntu CI runners)
# Python environment is already set up via setup-python action
rpmbuild -ba ${BUILD_DIR}/SPECS/sql-schema-studio.spec --nodeps

# -----------------------------------------------------------------------------
# 10. Copy the built RPM to project root
# -----------------------------------------------------------------------------
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ RPM built successfully!"
    echo ""
    
    # Copy to current directory
    find ${BUILD_DIR}/RPMS -name "*.rpm" -type f -exec cp {} "$PROJECT_ROOT" \;
    
    echo "📦 RPM files in project root:"
    ls -la "$PROJECT_ROOT"/*.rpm 2>/dev/null || echo "  (none found)"
    echo ""
    echo "Install with:"
    echo "  sudo dnf install $PROJECT_ROOT/sql-schema-studio-${VERSION}-1.*.rpm"
    echo ""
    echo "After installation, install Python dependencies:"
    echo "  sql-schema-studio-install-deps"
else
    echo ""
    echo "❌ RPM build failed!"
    exit 1
fi
