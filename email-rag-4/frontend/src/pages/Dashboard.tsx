/**
 * Dashboard Page
 *
 * Main dashboard with system stats, recent activity, and quick actions.
 */

import { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  CircularProgress,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemButton,
  Chip,
  Button,
  Card,
  CardContent,
  CardActions,
  Divider,
  Skeleton,
  Alert,
} from '@mui/material';
import {
  Email as EmailIcon,
  AttachFile,
  Folder,
  CloudUpload,
  Search as SearchIcon,
  Chat as ChatIcon,
  CheckCircle,
  Error as ErrorIcon,
  Schedule,
  Storage,
  TrendingUp,
  ArrowForward,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { statsApi, uploadApi } from '@/services/api';
import { formatFileSize, formatRelativeTime } from '@/utils';
import { useTaskProgress } from '@/hooks';
import type { PSTFile, ProcessingTask } from '@/types';

interface StatCardProps {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color: string;
  loading?: boolean;
  subtitle?: string;
}

function StatCard({ title, value, icon, color, loading, subtitle }: StatCardProps) {
  return (
    <Paper
      sx={{
        p: 3,
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        height: '100%',
      }}
    >
      <Box
        sx={{
          width: 56,
          height: 56,
          borderRadius: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: `${color}20`,
          color: color,
          flexShrink: 0,
        }}
      >
        {icon}
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="body2" color="text.secondary" noWrap>
          {title}
        </Typography>
        {loading ? (
          <Skeleton width={80} height={40} />
        ) : (
          <Typography variant="h4" fontWeight={600}>
            {typeof value === 'number' ? value.toLocaleString() : value}
          </Typography>
        )}
        {subtitle && (
          <Typography variant="caption" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </Box>
    </Paper>
  );
}

interface QuickActionProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  onClick: () => void;
  color: string;
}

function QuickAction({ title, description, icon, onClick, color }: QuickActionProps) {
  return (
    <Card
      sx={{
        height: '100%',
        cursor: 'pointer',
        transition: 'transform 0.2s, box-shadow 0.2s',
        '&:hover': {
          transform: 'translateY(-2px)',
          boxShadow: 4,
        },
      }}
      onClick={onClick}
    >
      <CardContent>
        <Box
          sx={{
            width: 48,
            height: 48,
            borderRadius: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: `${color}20`,
            color: color,
            mb: 2,
          }}
        >
          {icon}
        </Box>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {description}
        </Typography>
      </CardContent>
      <CardActions>
        <Button size="small" endIcon={<ArrowForward />}>
          Go
        </Button>
      </CardActions>
    </Card>
  );
}

interface ProcessingTaskItemProps {
  task: ProcessingTask;
  pstFile?: PSTFile;
}

function ProcessingTaskItem({ task, pstFile }: ProcessingTaskItemProps) {
  const progress = useTaskProgress(task.status === 'running' ? task.id : null);
  const currentProgress = progress?.progress ?? task.progress;

  const getStatusIcon = () => {
    switch (task.status) {
      case 'completed':
        return <CheckCircle color="success" />;
      case 'failed':
      case 'cancelled':
        return <ErrorIcon color="error" />;
      case 'running':
        return <CircularProgress size={24} />;
      default:
        return <Schedule color="action" />;
    }
  };

  const getStatusColor = (): 'success' | 'error' | 'warning' | 'default' => {
    switch (task.status) {
      case 'completed':
        return 'success';
      case 'failed':
      case 'cancelled':
        return 'error';
      case 'running':
        return 'warning';
      default:
        return 'default';
    }
  };

  return (
    <ListItem
      sx={{
        flexDirection: 'column',
        alignItems: 'stretch',
        gap: 1,
        py: 2,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
        <ListItemIcon sx={{ minWidth: 'auto' }}>
          {getStatusIcon()}
        </ListItemIcon>
        <ListItemText
          primary={pstFile?.original_filename || task.task_type}
          secondary={task.message || formatRelativeTime(task.created_at)}
          primaryTypographyProps={{ noWrap: true }}
          secondaryTypographyProps={{ noWrap: true }}
        />
        <Chip
          label={task.status}
          color={getStatusColor()}
          size="small"
          variant="outlined"
        />
      </Box>
      {task.status === 'running' && (
        <Box sx={{ width: '100%' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="caption" color="text.secondary">
              {progress?.message || 'Processing...'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {currentProgress}%
            </Typography>
          </Box>
          <LinearProgress variant="determinate" value={currentProgress} />
        </Box>
      )}
    </ListItem>
  );
}

export function Dashboard() {
  const navigate = useNavigate();
  const [showAllTasks, setShowAllTasks] = useState(false);

  const { data: stats, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: statsApi.getDashboardStats,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const { data: pstFiles, isLoading: filesLoading } = useQuery({
    queryKey: ['pst-files'],
    queryFn: uploadApi.getPSTFiles,
  });

  // Get recent processing tasks from PST files
  const processingTasks: ProcessingTask[] = pstFiles
    ?.filter((f) => f.status === 'processing')
    .map((f) => ({
      id: f.id,
      task_type: 'pst_processing',
      status: 'running' as const,
      progress: 0,
      message: `Processing ${f.original_filename}`,
      result: null,
      error: null,
      created_at: f.created_at,
      started_at: f.created_at,
      completed_at: null,
    })) || [];

  // Recent files (completed or failed)
  const recentFiles = pstFiles
    ?.filter((f) => f.status === 'completed' || f.status === 'failed')
    .slice(0, showAllTasks ? 10 : 5) || [];

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Dashboard
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
        Welcome back! Here's an overview of your email analysis system.
      </Typography>

      {statsError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to load dashboard stats. Please try again.
        </Alert>
      )}

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Emails"
            value={stats?.total_emails ?? 0}
            icon={<EmailIcon fontSize="large" />}
            color="#6366f1"
            loading={statsLoading}
            subtitle={stats?.emails_with_attachments ? `${stats.emails_with_attachments.toLocaleString()} with attachments` : undefined}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="PST Files"
            value={stats?.total_pst_files ?? 0}
            icon={<Folder fontSize="large" />}
            color="#10b981"
            loading={statsLoading}
            subtitle={stats?.completed_tasks ? `${stats.completed_tasks} processed` : undefined}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Attachments"
            value={stats?.total_attachments ?? 0}
            icon={<AttachFile fontSize="large" />}
            color="#f59e0b"
            loading={statsLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Storage Used"
            value={formatFileSize(stats?.storage_used ?? 0)}
            icon={<Storage fontSize="large" />}
            color="#3b82f6"
            loading={statsLoading}
          />
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        {/* Quick Actions */}
        <Grid item xs={12} md={8}>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <TrendingUp fontSize="small" />
            Quick Actions
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={4}>
              <QuickAction
                title="Upload PST"
                description="Upload new PST files for analysis"
                icon={<CloudUpload />}
                onClick={() => navigate('/upload')}
                color="#6366f1"
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <QuickAction
                title="Search Emails"
                description="Find emails using advanced search"
                icon={<SearchIcon />}
                onClick={() => navigate('/search')}
                color="#10b981"
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <QuickAction
                title="Chat with AI"
                description="Ask questions about your emails"
                icon={<ChatIcon />}
                onClick={() => navigate('/chat')}
                color="#f59e0b"
              />
            </Grid>
          </Grid>
        </Grid>

        {/* Recent Activity */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Recent Activity
            </Typography>
            <Divider sx={{ mb: 1 }} />

            {filesLoading ? (
              <Box sx={{ p: 2 }}>
                <Skeleton variant="rectangular" height={60} sx={{ mb: 1 }} />
                <Skeleton variant="rectangular" height={60} sx={{ mb: 1 }} />
                <Skeleton variant="rectangular" height={60} />
              </Box>
            ) : processingTasks.length === 0 && recentFiles.length === 0 ? (
              <Box sx={{ p: 3, textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary">
                  No recent activity. Upload a PST file to get started.
                </Typography>
                <Button
                  variant="contained"
                  size="small"
                  sx={{ mt: 2 }}
                  onClick={() => navigate('/upload')}
                >
                  Upload PST
                </Button>
              </Box>
            ) : (
              <List dense disablePadding>
                {/* Active processing tasks */}
                {processingTasks.map((task) => (
                  <ProcessingTaskItem
                    key={task.id}
                    task={task}
                    pstFile={pstFiles?.find((f) => f.id === task.id)}
                  />
                ))}

                {/* Recent completed/failed files */}
                {recentFiles.map((file) => (
                  <ListItemButton
                    key={file.id}
                    sx={{ borderRadius: 1 }}
                    onClick={() => navigate('/search')}
                  >
                    <ListItemIcon sx={{ minWidth: 40 }}>
                      {file.status === 'completed' ? (
                        <CheckCircle color="success" fontSize="small" />
                      ) : (
                        <ErrorIcon color="error" fontSize="small" />
                      )}
                    </ListItemIcon>
                    <ListItemText
                      primary={file.original_filename}
                      secondary={
                        file.status === 'completed'
                          ? `${(file.email_count ?? 0).toLocaleString()} emails`
                          : file.error_message || 'Processing failed'
                      }
                      primaryTypographyProps={{ noWrap: true, variant: 'body2' }}
                      secondaryTypographyProps={{ noWrap: true }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      {formatRelativeTime(file.processed_at || file.created_at)}
                    </Typography>
                  </ListItemButton>
                ))}

                {recentFiles.length >= 5 && !showAllTasks && (
                  <ListItem>
                    <Button
                      size="small"
                      fullWidth
                      onClick={() => setShowAllTasks(true)}
                    >
                      Show More
                    </Button>
                  </ListItem>
                )}
              </List>
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* System Health (Optional section for admins) */}
      {stats && stats.processing_tasks > 0 && (
        <Box sx={{ mt: 4 }}>
          <Alert severity="info" icon={<Schedule />}>
            {stats.processing_tasks} file{stats.processing_tasks > 1 ? 's' : ''} currently being processed.
            Check the recent activity panel for details.
          </Alert>
        </Box>
      )}
    </Box>
  );
}
