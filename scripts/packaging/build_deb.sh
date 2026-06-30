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

# Copy Python source files as package
mkdir -p ${BUILD_DIR}/${DEB_NAME}/usr/lib/python3/dist-packages/src
cp -r src/* ${BUILD_DIR}/${DEB_NAME}/usr/lib/python3/dist-packages/src/

# Remove __pycache__ if any
find ${BUILD_DIR}/${DEB_NAME} -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Install icon
ICON_SRC="src/resources/ui/icons/logo.svg"
if [ -f "$ICON_SRC" ]; then
    mkdir -p ${BUILD_DIR}/${DEB_NAME}/usr/share/icons/hicolor/scalable/apps/
    cp $ICON_SRC ${BUILD_DIR}/${DEB_NAME}/usr/share/icons/hicolor/scalable/apps/sql-schema-studio.svg
else
    echo "Warning: Icon not found at $ICON_SRC"
fi

# Install desktop file
DESKTOP_SRC="src/resources/desktop/sql-schema-studio.desktop"
if [ -f "$DESKTOP_SRC" ]; then
    mkdir -p ${BUILD_DIR}/${DEB_NAME}/usr/share/applications/
    cp $DESKTOP_SRC ${BUILD_DIR}/${DEB_NAME}/usr/share/applications/
    echo "Desktop file installed from $DESKTOP_SRC"
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

# Create launcher script
cat > ${BUILD_DIR}/${DEB_NAME}/usr/bin/sql-schema-studio << 'LAUNCHER'
#!/bin/bash
# SQL Schema Studio Launcher
exec python3 -m src.main "$@"
LAUNCHER
chmod +x ${BUILD_DIR}/${DEB_NAME}/usr/bin/sql-schema-studio

# Create control file with correct dependencies
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
         libvte-2.91-gtk4-dev       
Recommends: pipx
Suggests: python3-faker, python3-kbcstorage
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
License: GPL-3.0-or-later
Homepage: https://github.com/peter-leukanic/sql-schema-studio
EOF

# Create post-installation script to suggest optional packages
cat > ${BUILD_DIR}/${DEB_NAME}/DEBIAN/postinst << 'POSTINST'
#!/bin/bash
set -e

echo "SQL Schema Studio installed successfully!"
echo ""
echo "To install optional dependencies for additional features:"
echo "  sudo apt install python3-faker python3-kbcstorage"
echo ""
echo "Or use pipx for user-level installation:"
echo "  pipx install faker kbcstorage scikit-learn --include-deps"
echo ""
echo "Run with: sql-schema-studio"
POSTINST
chmod +x ${BUILD_DIR}/${DEB_NAME}/DEBIAN/postinst

# Build the package
dpkg-deb --build ${BUILD_DIR}/${DEB_NAME}

# Move to current directory
mv ${BUILD_DIR}/${DEB_NAME}.deb .

echo "✅ DEB built: ${DEB_NAME}.deb"
echo "Install with: sudo dpkg -i ${DEB_NAME}.deb"
echo "If dependencies fail, run: sudo apt --fix-broken install"
echo ""
echo " Other dependencies (install after package):"
echo "  pip install polars  --break-system-packages"
echo "  pipx install faker kbcstorage scikit-learn --include-deps"
echo "  sudo apt install python3-faker python3-kbcstorage"
