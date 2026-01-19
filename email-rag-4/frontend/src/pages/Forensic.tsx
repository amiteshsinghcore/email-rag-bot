/**
 * Forensic Page
 *
 * Displays audit logs, evidence files, and timeline analysis.
 */

import { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  IconButton,
  Tooltip,
  Alert,
  Skeleton,
  Button,
  Card,
  CardContent,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
} from '@mui/material';
import {
  History,
  Verified,
  VerifiedUser,
  Warning,
  Refresh,
  Timeline as TimelineIcon,
  Person,
  Email,
  CheckCircle,
  Shield,
  Fingerprint,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { forensicApi } from '@/services/api';
import { formatDateTime, formatFileSize } from '@/utils';
import type { EvidenceFile } from '@/types';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <div role="tabpanel" hidden={value !== index}>
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

function AuditLogsTab() {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['audit-logs', page, rowsPerPage],
    queryFn: () => forensicApi.getAuditLogs(page + 1, rowsPerPage),
  });

  const getActionColor = (action: string): 'default' | 'primary' | 'secondary' | 'error' | 'warning' | 'info' | 'success' => {
    switch (action.toLowerCase()) {
      case 'login': return 'success';
      case 'logout': return 'info';
      case 'delete': return 'error';
      case 'upload': return 'primary';
      case 'view': return 'default';
      case 'search': return 'secondary';
      default: return 'default';
    }
  };

  if (isLoading) {
    return (
      <Box>
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} variant="rectangular" height={60} sx={{ mb: 1 }} />
        ))}
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">
          <History sx={{ mr: 1, verticalAlign: 'middle' }} />
          Audit Trail
        </Typography>
        <Tooltip title="Refresh">
          <IconButton onClick={() => refetch()}>
            <Refresh />
          </IconButton>
        </Tooltip>
      </Box>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Timestamp</TableCell>
              <TableCell>User</TableCell>
              <TableCell>Action</TableCell>
              <TableCell>Resource</TableCell>
              <TableCell>IP Address</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data?.items.map((log) => (
              <TableRow key={log.id} hover>
                <TableCell>
                  <Typography variant="body2">
                    {formatDateTime(log.created_at)}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Person fontSize="small" color="action" />
                    <Typography variant="body2">{log.user_email}</Typography>
                  </Box>
                </TableCell>
                <TableCell>
                  <Chip
                    label={log.action}
                    size="small"
                    color={getActionColor(log.action)}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>
                  <Typography variant="body2" color="text.secondary">
                    {log.resource_type}
                    {log.resource_id && ` #${log.resource_id.slice(0, 8)}...`}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" color="text.secondary">
                    {log.ip_address || '-'}
                  </Typography>
                </TableCell>
              </TableRow>
            ))}
            {(!data?.items || data.items.length === 0) && (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  <Typography color="text.secondary" sx={{ py: 4 }}>
                    No audit logs found
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        <TablePagination
          component="div"
          count={data?.total || 0}
          page={page}
          onPageChange={(_, newPage) => setPage(newPage)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={(e) => {
            setRowsPerPage(parseInt(e.target.value, 10));
            setPage(0);
          }}
          rowsPerPageOptions={[10, 25, 50, 100]}
        />
      </TableContainer>
    </Box>
  );
}

interface EvidenceCardProps {
  evidence: EvidenceFile;
  onVerify: () => void;
  isVerifying: boolean;
}

function EvidenceCard({ evidence, onVerify, isVerifying }: EvidenceCardProps) {
  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Shield color={evidence.is_verified ? 'success' : 'warning'} sx={{ fontSize: 40 }} />
            <Box>
              <Typography variant="h6">{evidence.filename}</Typography>
              <Typography variant="body2" color="text.secondary">
                {formatFileSize(evidence.file_size)} | Registered {formatDateTime(evidence.registered_at)}
              </Typography>
            </Box>
          </Box>
          <Chip
            icon={evidence.is_verified ? <CheckCircle /> : <Warning />}
            label={evidence.is_verified ? 'Verified' : 'Unverified'}
            color={evidence.is_verified ? 'success' : 'warning'}
            variant="outlined"
          />
        </Box>

        <Divider sx={{ my: 2 }} />

        <Box sx={{ display: 'flex', gap: 4 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">SHA-256</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
              {evidence.sha256_hash}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">MD5</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
              {evidence.md5_hash}
            </Typography>
          </Box>
        </Box>

        {evidence.chain_of_custody.length > 0 && (
          <>
            <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
              Chain of Custody
            </Typography>
            <List dense disablePadding>
              {evidence.chain_of_custody.slice(0, 3).map((entry, idx) => (
                <ListItem key={idx} disablePadding sx={{ py: 0.5 }}>
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    <Fingerprint fontSize="small" color="action" />
                  </ListItemIcon>
                  <ListItemText
                    primary={entry.action}
                    secondary={`${entry.user_email} - ${formatDateTime(entry.timestamp)}`}
                    primaryTypographyProps={{ variant: 'body2' }}
                    secondaryTypographyProps={{ variant: 'caption' }}
                  />
                </ListItem>
              ))}
            </List>
          </>
        )}

        <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            variant="outlined"
            size="small"
            startIcon={<VerifiedUser />}
            onClick={onVerify}
            disabled={isVerifying}
          >
            {isVerifying ? 'Verifying...' : 'Verify Integrity'}
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}

function EvidenceTab() {
  const queryClient = useQueryClient();
  const [verifyingId, setVerifyingId] = useState<string | null>(null);

  const { data: evidence, isLoading, refetch } = useQuery({
    queryKey: ['evidence'],
    queryFn: forensicApi.getEvidence,
  });

  const verifyMutation = useMutation({
    mutationFn: forensicApi.verifyEvidence,
    onSuccess: (result) => {
      if (result.is_valid) {
        toast.success('Evidence integrity verified successfully');
      } else {
        toast.error(`Integrity check failed: ${result.message}`);
      }
      queryClient.invalidateQueries({ queryKey: ['evidence'] });
      setVerifyingId(null);
    },
    onError: (error: Error) => {
      toast.error(`Verification failed: ${error.message}`);
      setVerifyingId(null);
    },
  });

  const handleVerify = (id: string) => {
    setVerifyingId(id);
    verifyMutation.mutate(id);
  };

  if (isLoading) {
    return (
      <Box>
        {[1, 2].map((i) => (
          <Skeleton key={i} variant="rectangular" height={200} sx={{ mb: 2 }} />
        ))}
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">
          <Verified sx={{ mr: 1, verticalAlign: 'middle' }} />
          Evidence Files
        </Typography>
        <Tooltip title="Refresh">
          <IconButton onClick={() => refetch()}>
            <Refresh />
          </IconButton>
        </Tooltip>
      </Box>

      {evidence && evidence.length > 0 ? (
        evidence.map((item) => (
          <EvidenceCard
            key={item.id}
            evidence={item}
            onVerify={() => handleVerify(item.id)}
            isVerifying={verifyingId === item.id}
          />
        ))
      ) : (
        <Alert severity="info">
          No evidence files registered. Upload PST files to register them as evidence.
        </Alert>
      )}
    </Box>
  );
}

function TimelineTab() {
  const { data: timeline, isLoading, refetch } = useQuery({
    queryKey: ['timeline'],
    queryFn: () => forensicApi.getTimeline(),
  });

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'sent': return <Email color="primary" />;
      case 'received': return <Email color="success" />;
      case 'replied': return <Email color="info" />;
      case 'forwarded': return <Email color="secondary" />;
      default: return <Email color="action" />;
    }
  };

  if (isLoading) {
    return (
      <Box>
        <LinearProgress sx={{ mb: 2 }} />
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} variant="rectangular" height={80} sx={{ mb: 1 }} />
        ))}
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">
          <TimelineIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          Email Timeline
        </Typography>
        <Tooltip title="Refresh">
          <IconButton onClick={() => refetch()}>
            <Refresh />
          </IconButton>
        </Tooltip>
      </Box>

      {timeline && timeline.length > 0 ? (
        <Paper sx={{ p: 2 }}>
          <List>
            {timeline.map((event) => (
              <ListItem
                key={event.id}
                sx={{
                  borderLeft: '2px solid',
                  borderColor: 'primary.main',
                  ml: 2,
                  pl: 2,
                  position: 'relative',
                  '&::before': {
                    content: '""',
                    position: 'absolute',
                    left: -6,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    bgcolor: 'primary.main',
                  },
                }}
              >
                <ListItemIcon>
                  {getEventIcon(event.event_type)}
                </ListItemIcon>
                <ListItemText
                  primary={event.subject || '(No Subject)'}
                  secondary={
                    <Box>
                      <Typography variant="caption" display="block">
                        {event.sender} → {event.recipients.join(', ')}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {formatDateTime(event.date_sent)}
                      </Typography>
                    </Box>
                  }
                />
                <Chip label={event.event_type} size="small" variant="outlined" />
              </ListItem>
            ))}
          </List>
        </Paper>
      ) : (
        <Alert severity="info">
          No timeline data available. Upload and process PST files to see email timeline.
        </Alert>
      )}
    </Box>
  );
}

export function Forensic() {
  const [tabValue, setTabValue] = useState(0);

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Forensic Analysis
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        Audit logs, evidence management, and timeline analysis for email forensics.
      </Typography>

      <Paper sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={tabValue} onChange={(_, v) => setTabValue(v)}>
          <Tab icon={<History />} label="Audit Logs" />
          <Tab icon={<Shield />} label="Evidence" />
          <Tab icon={<TimelineIcon />} label="Timeline" />
        </Tabs>
      </Paper>

      <TabPanel value={tabValue} index={0}>
        <AuditLogsTab />
      </TabPanel>

      <TabPanel value={tabValue} index={1}>
        <EvidenceTab />
      </TabPanel>

      <TabPanel value={tabValue} index={2}>
        <TimelineTab />
      </TabPanel>
    </Box>
  );
}
