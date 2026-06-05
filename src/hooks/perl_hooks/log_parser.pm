# ----------------------------------------------------------------------
# SQL Schema Studio 0.8 - PostgreSQL Log Analyzer (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

package log_parser;
use strict;
use warnings;
use DBI;
use JSON;
use Text::CSV;

sub new {
    my $class = shift;
    my $self = {};
    bless $self, $class;
    return $self;
}

sub get_metadata {
    return {
        name => 'PostgreSQL Log Analyzer',
        version => '2.0.0',
        author => 'SQL Schema Studio',
        description => 'Advanced PostgreSQL log analysis with CSV support and remote reading',
        triggers => ['scheduled.interval'],
    };
}

sub execute {
    my ($self, $context) = @_;
    
    # Extract connection string from context
    my $conn_string = '';
    if (ref($context) eq 'HASH' && $context->{data}) {
        $conn_string = $context->{data}{conn_string} || '';
    } elsif ($context && ref($context) eq 'HookContext') {
        # Try to get data via method if available
        $conn_string = $context->{data}{conn_string} if $context->can('get_data');
    }
    
    return $self->execute_sync($conn_string);
}

sub execute_sync {
    my ($self, $conn_string) = @_;
    
    my $results = {
        status => 'ok',
        message => '',
        recommendations => [],
        error_samples => [],
    };
    
    # Try methods in order: 1) SQL remote, 2) Local text, 3) Local CSV
    my ($log_data, $method) = $self->_read_logs_via_sql($conn_string);

    unless ($log_data && @$log_data) {
	($log_data, $method) = $self->_read_logs_local_text();
    }

    unless ($log_data && @$log_data) {
	($log_data, $method) = $self->_read_logs_local_csv();
    }

    unless ($log_data && @$log_data) {
	$results->{status} = 'error';
	$results->{message} = 'No log entries found. Enable csvlog in postgresql.conf';
	return $results;
    }

    
    # Analyze parsed logs
    my $analysis = $self->_analyze_logs($log_data);
    
    $results->{message} = sprintf(
        "Analyzed %d log entries via %s, found %d issues",
        $analysis->{total_lines}, $method, $analysis->{issue_count}
    );
    $results->{recommendations} = $analysis->{recommendations};
    $results->{error_samples} = $analysis->{error_samples};
    $results->{error_categories} = $analysis->{error_categories};
    
    return $results;
}

# ============================================================
# METHOD 1: Remote SQL access (MOST PROFESSIONAL)
# ============================================================
sub _read_logs_via_sql {
    my ($self, $conn_string) = @_;
    my $csv = Text::CSV->new({ binary => 1, auto_diag => 1 });
    
    return (undef, undef) unless $conn_string;
    
    # Parse connection string
    my %conn_params;
    for my $part (split /\s+/, $conn_string) {
        my ($key, $val) = split /=/, $part, 2;
        $conn_params{$key} = $val if $key && $val;
    }
    
    my $dbh = DBI->connect(
        "DBI:Pg:dbname=$conn_params{dbname};host=$conn_params{host};port=$conn_params{port}",
        $conn_params{user},
        $conn_params{password},
        { RaiseError => 0, PrintError => 0 }
    );
    
    return (undef, undef) unless $dbh;
    
    # Check if pg_read_file is available (PostgreSQL 10+)
    my $has_pg_read = $dbh->selectrow_array(
        "SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'pg_read_file')"
    );
    
    unless ($has_pg_read) {
        $dbh->disconnect();
        return (undef, undef);
    }
    
    # Get current user and check pg_monitor role
    my $current_user = $dbh->selectrow_array("SELECT current_user");
    my $has_monitor_role = $dbh->selectrow_array(
        "SELECT pg_has_role('$current_user', 'pg_monitor', 'USAGE')"
    );
    
    unless ($has_monitor_role) {
        $dbh->disconnect();
        return (undef, undef);
    }
    
    # Find latest CSV log file using pg_ls_logdir
    my $log_file = $dbh->selectrow_array(q{
        SELECT filename FROM pg_ls_logdir() 
        WHERE filename LIKE '%.csv' 
        ORDER BY modification DESC LIMIT 1
    });
    
    unless ($log_file) {
        $dbh->disconnect();
        return (undef, undef);
    }
    
    # Read last 5000 lines from CSV log
    my $rows = $dbh->selectall_arrayref(
        "SELECT * FROM pg_read_file('pg_log/$log_file', 0, 500000)"
    );
    
    $dbh->disconnect();
    
    return (undef, undef) unless $rows && @$rows;
    
    # Parse CSV content
    my @log_entries;
    my $csv_content = $rows->[0][0];
    my @lines = split /\n/, $csv_content;
    
    # Get header
    my $header_line = shift @lines;
    $csv->parse($header_line);
    my @headers = $csv->fields();
    
    for my $line (@lines) {
        last if @log_entries >= 5000;
        next unless $line =~ /,/;
        
        $csv->parse($line);
	my @fields = $csv->fields();
        
        my %entry;
        for my $i (0 .. $#headers) {
            $entry{$headers[$i]} = $fields[$i] || '';
        }
        push @log_entries, \%entry;
    }
    
    return (\@log_entries, 'SQL (pg_read_file)');
}

sub _read_logs_local_csv {
    my ($self) = @_;
    
    my $log_dir = $self->_find_log_directory();
    return (undef, undef) unless $log_dir && -d $log_dir;
    
    # Filter .csv
    opendir(my $dh, $log_dir) or return (undef, undef);
    my @csv_files = grep { /\.csv$/i } readdir($dh);
    closedir($dh);
    
    return (undef, undef) unless @csv_files;
    
    @csv_files = sort { 
        (stat("$log_dir/$b"))[9] <=> (stat("$log_dir/$a"))[9] 
    } @csv_files;
    
    my $log_file = "$log_dir/$csv_files[0]";
    return (undef, undef) unless -r $log_file;
    
    # Switch to log dir
    my $test_dir = '/tmp/pg_test_logs';
    if (-d $test_dir && -r "$test_dir/latest.csv") {
        $log_file = "$test_dir/latest.csv";
    }
    
    open(my $fh, '<', $log_file) or return (undef, undef);
    my @log_entries;
    
    # For logs (not CSV) - using regex parsing
    while (my $line = <$fh>) {
        last if @log_entries >= 5000;
        chomp $line;
        next unless $line =~ /LOG|ERROR|FATAL|PANIC/;
        
        # Pars to standard PostgreSQL log format
        # 2026-06-05 11:40:51.151 CEST [36310] LOG:  ending
        if ($line =~ /^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s+\S+\s+\[(\d+)\]\s+(\w+):\s+(.*)$/) {
            push @log_entries, {
                log_time => $1,
                pid => $2,
                severity => $3,
                message => $4,
            };
        }
    }
    close($fh);
    
    return (\@log_entries, 'TEXT (local)') if @log_entries;
    return (undef, undef);
}

# ============================================================
# METHOD 3: Local text logs (fallback)
# ============================================================
sub _read_logs_local_text {
    my ($self) = @_;
    
    my $log_dir = $self->_find_log_directory();
    return (undef, undef) unless $log_dir && -d $log_dir;
    
    opendir(my $dh, $log_dir) or return (undef, undef);
    my @log_files = grep { /\.log$/i && !/\.csv$/i } readdir($dh);
    closedir($dh);
    
    return (undef, undef) unless @log_files;
    
    @log_files = sort { 
        (stat("$log_dir/$b"))[9] <=> (stat("$log_dir/$a"))[9] 
    } @log_files;
    
    my $log_file = "$log_dir/$log_files[0]";
    return (undef, undef) unless -r $log_file;
    
    open(my $fh, '<', $log_file) or return (undef, undef);
    my @log_entries;
    
    while (my $line = <$fh>) {
        last if @log_entries >= 5000;
        chomp $line;
        
        # Parse standard PostgreSQL log format
        if ($line =~ /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+).+?\[(\d+)\]\s+(\w+):\s+(.*)$/) {
            push @log_entries, {
                log_time => $1,
                pid => $2,
                severity => $3,
                message => $4,
            };
        }
    }
    close($fh);
    
    return (\@log_entries, 'TEXT (local)');
}

# ============================================================
# Find log directory (supports Fedora/RHEL/Debian/Ubuntu)
# ============================================================
sub _find_log_directory {
    my ($self) = @_;
    
    # Test logs (for development)
    return '/tmp/pg_test_logs' if -d '/tmp/pg_test_logs';
    
    # Fedora/RHEL/CentOS
    return '/var/lib/pgsql/data/log' if -d '/var/lib/pgsql/data/log';
    
    # Debian/Ubuntu
    return '/var/log/postgresql' if -d '/var/log/postgresql';
    
    return undef;
}

# ============================================================
# Log analysis with error categorization
# ============================================================
sub _analyze_logs {
    my ($self, $log_entries) = @_;
    
    my $analysis = {
        total_lines => scalar @$log_entries,
        issue_count => 0,
        recommendations => [],
        error_samples => [],
        error_categories => {},
    };
    
    my @errors;
    my @slow_queries;
    my %error_cats;
    
    for my $entry (@$log_entries) {
        my $severity = $entry->{error_severity} || $entry->{severity} || '';
        my $message = $entry->{message} || $entry->{error_message} || '';
        my $duration = $entry->{duration_ms} || 0;
        
        # Collect errors
        if ($severity eq 'ERROR' || $severity eq 'FATAL' || 
            $message =~ /ERROR:|FATAL:/i) {
            
            push @errors, {
                severity => $severity,
                message => $message,
                timestamp => $entry->{log_time} || '',
            };
            
            my $category = $self->_categorize_error($message);
            $error_cats{$category}++;
        }
        
        # Collect slow queries
        if ($duration > 1000 || ($message =~ /duration: (\d+) ms/ && $1 > 1000)) {
            push @slow_queries, {
                duration_ms => $duration || ($1 || 0),
                query => $message,
            };
        }
    }
    
    $analysis->{error_categories} = \%error_cats;
    
    # Error rate analysis
    my $error_rate = $analysis->{total_lines} > 0 ? 
        (scalar @errors) / $analysis->{total_lines} * 100 : 0;
    
    if ($error_rate > 5) {
        push @{$analysis->{recommendations}}, {
            table => 'PostgreSQL Log',
            priority => 'HIGH',
            action => 'Investigate error patterns',
            reason => sprintf("High error rate: %.1f%% (%d errors)", $error_rate, scalar @errors),
            sql => '-- Review error samples below for specific issues',
        };
        $analysis->{issue_count}++;
    }
    
    # Top error categories
    my @sorted = sort { $error_cats{$b} <=> $error_cats{$a} } keys %error_cats;
    for my $cat (@sorted[0 .. ($#sorted < 2 ? $#sorted : 2)]) {
        my $count = $error_cats{$cat};
        if ($count > 3) {
            push @{$analysis->{recommendations}}, {
                table => 'PostgreSQL Log',
                priority => $cat eq 'Authentication' ? 'HIGH' : 'MEDIUM',
                action => "Address $cat errors",
                reason => "$count $cat errors detected",
                sql => $self->_get_fix_sql($cat),
            };
            $analysis->{issue_count}++;
        }
    }
    
    # Slow queries
    if (@slow_queries > 0) {
        push @{$analysis->{recommendations}}, {
            table => 'PostgreSQL Log',
            priority => 'MEDIUM',
            action => 'Optimize slow queries',
            reason => sprintf("%d slow queries detected (>1s)", scalar @slow_queries),
            sql => '-- Enable pg_stat_statements to identify specific queries:
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;',
        };
        $analysis->{issue_count}++;
    }
    
    # Error samples (first 5)
    for my $err (@errors[0 .. ($#errors < 4 ? $#errors : 4)]) {
        push @{$analysis->{error_samples}}, $err->{message};
    }
    
    return $analysis;
}

sub _categorize_error {
    my ($message) = @_;
    $message = lc($message || '');
    
    return 'Connection' if $message =~ /connection/i;
    return 'Authentication' if $message =~ /password|authentication|ident|peer/i;
    return 'Permission' if $message =~ /permission denied|access denied/i;
    return 'Constraint' if $message =~ /constraint|violates|violation|foreign key|primary key|unique/i;
    return 'Syntax' if $message =~ /syntax error/i;
    return 'Resource' if $message =~ /out of memory|disk full|no space/i;
    return 'Deadlock' if $message =~ /deadlock/i;
    return 'Timeout' if $message =~ /timeout|canceling statement/i;
    return 'Relation' if $message =~ /relation.*does not exist|table.*does not exist/i;
    return 'Other';
}

sub _get_fix_sql {
    my ($category) = @_;
    
    my %fixes = (
        'Authentication' => '-- Check pg_hba.conf and user passwords:
sudo cat /var/lib/pgsql/data/pg_hba.conf
sudo -u postgres psql -c "ALTER USER username PASSWORD \'new_password\';"',
        'Constraint' => '-- Identify constraint violations:
SELECT * FROM pg_constraint WHERE conname LIKE \'%key%\';
-- Check data integrity before adding constraints',
        'Permission' => '-- Check table permissions:
GRANT SELECT, INSERT, UPDATE, DELETE ON table_name TO username;
-- Or check ownership:
ALTER TABLE table_name OWNER TO username;',
        'Relation' => '-- Table/relation does not exist:
CREATE TABLE IF NOT EXISTS missing_table (...);
-- Or fix schema search path:
SET search_path TO public,schema_name;',
        'Deadlock' => '-- Investigate deadlocks:
SELECT * FROM pg_locks WHERE NOT granted;
-- Consider retry logic in application with shorter transactions',
        'Timeout' => '-- Increase statement timeout for this session:
SET statement_timeout = \'5min\';
-- Or tune globally in postgresql.conf',
    );
    
    return $fixes{$category} || '-- Review PostgreSQL logs for specific error details';
}

1;
