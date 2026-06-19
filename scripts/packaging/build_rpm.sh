#!/bin/bash
# Build RPM package for SQL Schema Studio
set -e

# Get location of the TOML file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is in scripts/packaging/build_rpm.sh, so we move 2 levels up
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "Building RPM for SQL Schema Studio from $PROJECT_ROOT"

# Check if pyproject exists
if [ ! -f "pyproject.toml" ]; then
    echo "ERROR: pyproject.toml not found in $PROJECT_ROOT"
    echo "Current directory: $(pwd)"
    echo "Files: $(ls -la)"
    exit 1
fi

VERSION=$(grep "^version" pyproject.toml | head -1 | cut -d'"' -f2)
if [ -z "$VERSION" ]; then
    echo "ERROR: Could not find version in pyproject.toml"
    exit 1
fi

RELEASE=1
ARCH=noarch

echo "Version: $VERSION"

# Setup RPM build environment
BUILD_DIR=~/rpmbuild
mkdir -p ${BUILD_DIR}/{BUILD,RPMS,SOURCES,SPECS,SRPMS,BUILDROOT}

# Create source tarball
echo "Creating source tarball..."
tar --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' \
    -czf ${BUILD_DIR}/SOURCES/sql-schema-studio-${VERSION}.tar.gz \
    --transform "s/^/sql-schema-studio-${VERSION}\//" \
    src/ pyproject.toml README.md LICENSE 2>/dev/null

if [ ! -f "${BUILD_DIR}/SOURCES/sql-schema-studio-${VERSION}.tar.gz" ]; then
    echo "ERROR: Failed to create source tarball"
    exit 1
fi

# Get the actual date for the changelog
CHANGELOG_DATE=$(LC_TIME=C date +"%a %b %d %Y")

# Create spec file
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

Requires:       python3 >= 3.12
Requires:       python3-psycopg2
Requires:       python3-gobject
Requires:       python3-sqlparse
Requires:       python3-keyring
Requires:       python3-numpy
Requires:       python3-pandas
Requires:       python3-polars
Requires:       python3-scikit-learn
Requires:       python3-matplotlib
Requires:       python3-cairo
Requires:       python3-paramiko
Requires:       python3-faker
Requires:       python3-kbcstorage
Requires:       gtk4
Requires:       gtksourceview5

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
# Create Python package directory
mkdir -p %{buildroot}%{python3_sitelib}/sql_schema_studio
cp -r src/* %{buildroot}%{python3_sitelib}/sql_schema_studio/

# Remove __pycache__
find %{buildroot} -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Install icon
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/
if [ -f "src/resources/ui/icons/logo.svg" ]; then
    cp src/resources/ui/icons/logo.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/sql-schema-studio.svg
fi

# Install desktop file
mkdir -p %{buildroot}%{_datadir}/applications/
if [ -f "src/resources/desktop/sql-schema-studio.desktop" ]; then
    cp src/resources/desktop/sql-schema-studio.desktop %{buildroot}%{_datadir}/applications/
else
    cat > %{buildroot}%{_datadir}/applications/sql-schema-studio.desktop << 'DESKTOP_EOF'
[Desktop Entry]
Name=SQL Schema Studio
Comment=Intelligent PostgreSQL Management Platform
Exec=%{_bindir}/sql-schema-studio
Icon=sql-schema-studio
Terminal=false
Type=Application
Categories=Development;Database;IDE;
StartupWMClass=SQL Schema Studio
MimeType=text/x-sql;
DESKTOP_EOF
fi

# Create launcher script
mkdir -p %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/sql-schema-studio << 'LAUNCHER_EOF'
#!/bin/bash
exec python3 -m sql_schema_studio.main "$@"
LAUNCHER_EOF
chmod 755 %{buildroot}%{_bindir}/sql-schema-studio

%files
%{python3_sitelib}/sql_schema_studio/
%{_bindir}/sql-schema-studio
%{_datadir}/icons/hicolor/scalable/apps/sql-schema-studio.svg
%{_datadir}/applications/sql-schema-studio.desktop

%doc README.md LICENSE

%changelog
* CHANGELOG_DATE_PLACEHOLDER Peter Leukanič <peter@leukanic.eu> - VERSION_PLACEHOLDER-1
- Release vVERSION_PLACEHOLDER
SPEC_EOF

# Replace placeholderls
sed -i "s/VERSION_PLACEHOLDER/${VERSION}/g" ${BUILD_DIR}/SPECS/sql-schema-studio.spec
sed -i "s/CHANGELOG_DATE_PLACEHOLDER/${CHANGELOG_DATE}/g" ${BUILD_DIR}/SPECS/sql-schema-studio.spec

echo "Building RPM..."
# Build RPM
rpmbuild -ba ${BUILD_DIR}/SPECS/sql-schema-studio.spec --nodeps

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
else
    echo ""
    echo "❌ RPM build failed!"
    exit 1
fi
