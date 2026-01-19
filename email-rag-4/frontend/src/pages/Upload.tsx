/**
 * Upload Page
 *
 * PST file upload interface with drag-and-drop and progress tracking.
 */

import { useState, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  IconButton,
  Chip,
  Alert,
  AlertTitle,
  Collapse,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Grid,
  Tooltip,
} from '@mui/material';
import {
  CloudUpload,
  InsertDriveFile,
  CheckCircle,
  Error as ErrorIcon,
  Cancel,
  Delete,
  Folder,
  Refresh,
  Info,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { uploadApi } from '@/services/api';
import { useTaskProgress } from '@/hooks';
import { formatFileSize, formatRelativeTime } from '@/utils';
import type { PSTFile } from '@/types';

interface UploadingFile {
  file: File;
  progress: number;
  status: 'uploading' | 'processing' | 'completed' | 'failed';
  taskId?: string;
  pstFileId?: string;
  error?: string;
}

interface DropZoneProps {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
}

function DropZone({ onFilesSelected, disabled }: DropZoneProps) {
  const [isDragActive, setIsDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragIn = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragActive(true);
    }
  }, []);

  const handleDragOut = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragActive(false);

      if (disabled) return;

      const files = Array.from(e.dataTransfer.files).filter(
        (file) =>
          file.name.toLowerCase().endsWith('.pst') ||
          file.name.toLowerCase().endsWith('.ost')
      );

      if (files.length > 0) {
        onFilesSelected(files);
      } else {
        toast.error('Please drop PST or OST files only');
      }
    },
    [onFilesSelected, disabled]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        onFilesSelected(Array.from(e.target.files));
      }
      // Reset input
      if (inputRef.current) {
        inputRef.current.value = '';
      }
    },
    [onFilesSelected]
  );

  return (
    <Paper
      onDragEnter={handleDragIn}
      onDragLeave={handleDragOut}
      onDragOver={handleDrag}
      onDrop={handleDrop}
      sx={{
        p: 6,
        textAlign: 'center',
        border: '2px dashed',
        borderColor: isDragActive ? 'primary.main' : 'divider',
        bgcolor: isDragActive ? 'action.hover' : 'background.paper',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        transition: 'all 0.2s ease',
        '&:hover': disabled
          ? {}
          : {
            borderColor: 'primary.main',
            bgcolor: 'action.hover',
          },
      }}
      onClick={() => !disabled && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pst,.ost"
        multiple
        onChange={handleFileInput}
        style={{ display: 'none' }}
        disabled={disabled}
      />
      <CloudUpload
        sx={{
          fontSize: 64,
          color: isDragActive ? 'primary.main' : 'text.secondary',
          mb: 2,
        }}
      />
      <Typography variant="h6" gutterBottom>
        {isDragActive ? 'Drop files here' : 'Drag & drop PST files here'}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        or click to browse your files
      </Typography>
      <Button
        variant="contained"
        startIcon={<CloudUpload />}
        disabled={disabled}
        onClick={(e) => {
          e.stopPropagation();
          inputRef.current?.click();
        }}
      >
        Select Files
      </Button>
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 2 }}>
        Supported formats: .pst, .ost (Maximum 50GB per file)
      </Typography>
    </Paper>
  );
}

// Processing stages with descriptions
const PROCESSING_STAGES = [
  { key: 'uploading', label: 'Uploading', icon: CloudUpload, progress: [0, 5] },
  { key: 'validating', label: 'Validating', icon: InsertDriveFile, progress: [5, 10] },
  { key: 'parsing', label: 'Parsing PST', icon: Folder, progress: [10, 20] },
  { key: 'extracting', label: 'Extracting Emails', icon: InsertDriveFile, progress: [20, 50] },
  { key: 'embedding', label: 'Creating Embeddings', icon: InsertDriveFile, progress: [50, 80] },
  { key: 'indexing', label: 'Indexing for Search', icon: InsertDriveFile, progress: [80, 95] },
  { key: 'completed', label: 'Complete', icon: CheckCircle, progress: [100, 100] },
];

function getStageFromProgress(progress: number): string {
  for (const stage of PROCESSING_STAGES) {
    if (progress >= stage.progress[0] && progress < stage.progress[1]) {
      return stage.key;
    }
  }
  return progress >= 100 ? 'completed' : 'processing';
}

interface UploadProgressItemProps {
  upload: UploadingFile;
  onCancel: () => void;
}

function UploadProgressItem({ upload, onCancel }: UploadProgressItemProps) {
  const taskProgress = useTaskProgress(
    upload.status === 'processing' && upload.taskId ? upload.taskId : null
  );

  const displayProgress =
    upload.status === 'processing' && taskProgress
      ? taskProgress.progress
      : upload.progress;

  const currentStage = upload.status === 'processing'
    ? getStageFromProgress(displayProgress)
    : upload.status;

  const displayMessage =
    upload.status === 'processing' && taskProgress
      ? taskProgress.message
      : upload.status === 'uploading'
        ? `Uploading... ${upload.progress}%`
        : upload.status === 'completed'
          ? 'Completed'
          : upload.error || 'Failed';

  const getStatusIcon = () => {
    switch (upload.status) {
      case 'completed':
        return <CheckCircle color="success" />;
      case 'failed':
        return <ErrorIcon color="error" />;
      default:
        return <InsertDriveFile color="primary" />;
    }
  };

  const getStatusColor = (): 'success' | 'error' | 'warning' | 'primary' => {
    switch (upload.status) {
      case 'completed':
        return 'success';
      case 'failed':
        return 'error';
      case 'processing':
        return 'warning';
      default:
        return 'primary';
    }
  };

  return (
    <ListItem
      sx={{
        flexDirection: 'column',
        alignItems: 'stretch',
        gap: 1,
        py: 2,
        borderBottom: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
        <ListItemIcon sx={{ minWidth: 40 }}>{getStatusIcon()}</ListItemIcon>
        <ListItemText
          primary={upload.file.name}
          secondary={formatFileSize(upload.file.size)}
          primaryTypographyProps={{ noWrap: true }}
        />
        <Chip
          label={upload.status}
          color={getStatusColor()}
          size="small"
          variant="outlined"
        />
        {(upload.status === 'uploading' || upload.status === 'processing') && (
          <ListItemSecondaryAction>
            <Tooltip title="Cancel">
              <IconButton edge="end" onClick={onCancel} size="small">
                <Cancel />
              </IconButton>
            </Tooltip>
          </ListItemSecondaryAction>
        )}
      </Box>

      {(upload.status === 'uploading' || upload.status === 'processing') && (
        <Box sx={{ width: '100%' }}>
          {/* Stage indicators */}
          <Box sx={{ display: 'flex', gap: 0.5, mb: 1.5, flexWrap: 'wrap' }}>
            {PROCESSING_STAGES.slice(0, -1).map((stage) => {
              const isActive = currentStage === stage.key;
              const isComplete = displayProgress > stage.progress[1];
              return (
                <Chip
                  key={stage.key}
                  label={stage.label}
                  size="small"
                  color={isComplete ? 'success' : isActive ? 'primary' : 'default'}
                  variant={isActive ? 'filled' : 'outlined'}
                  sx={{
                    fontSize: '0.7rem',
                    height: 22,
                    opacity: isComplete || isActive ? 1 : 0.5,
                  }}
                />
              );
            })}
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="caption" color="text.secondary">
              {displayMessage}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {Math.round(displayProgress)}%
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={displayProgress}
            color={getStatusColor()}
          />
        </Box>
      )}

      {upload.status === 'failed' && upload.error && (
        <Alert severity="error" sx={{ mt: 1 }}>
          {upload.error}
        </Alert>
      )}
    </ListItem>
  );
}

interface PSTFileItemProps {
  file: PSTFile;
  onDelete: () => void;
}

function PSTFileItem({ file, onDelete }: PSTFileItemProps) {
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const taskProgress = useTaskProgress(
    ['uploading', 'validating', 'parsing', 'extracting', 'embedding', 'indexing', 'processing'].includes(file.status)
      ? file.id
      : null
  );

  const isProcessing = ['uploading', 'validating', 'parsing', 'extracting', 'embedding', 'indexing', 'processing'].includes(file.status);
  const displayProgress = taskProgress?.progress ?? file.progress ?? 0;

  const getStatusIcon = () => {
    switch (file.status) {
      case 'completed':
        return <CheckCircle color="success" />;
      case 'failed':
      case 'cancelled':
        return <ErrorIcon color="error" />;
      case 'uploading':
      case 'validating':
      case 'parsing':
      case 'extracting':
      case 'embedding':
      case 'indexing':
      case 'processing':
        return <Refresh color="warning" sx={{ animation: 'spin 1s linear infinite' }} />;
      default:
        return <Folder color="action" />;
    }
  };

  const getStatusColor = (): 'success' | 'error' | 'warning' | 'default' => {
    switch (file.status) {
      case 'completed':
        return 'success';
      case 'failed':
      case 'cancelled':
        return 'error';
      case 'uploading':
      case 'validating':
      case 'parsing':
      case 'extracting':
      case 'embedding':
      case 'indexing':
      case 'processing':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getStatusLabel = () => {
    if (file.current_phase) {
      return file.current_phase.charAt(0).toUpperCase() + file.current_phase.slice(1);
    }
    return file.status.charAt(0).toUpperCase() + file.status.slice(1);
  };

  return (
    <>
      <ListItem
        sx={{
          bgcolor: 'background.paper',
          borderRadius: 1,
          mb: 1,
          border: '1px solid',
          borderColor: 'divider',
          flexDirection: 'column',
          alignItems: 'stretch',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
          <ListItemIcon sx={{ minWidth: 40 }}>{getStatusIcon()}</ListItemIcon>
          <ListItemText
            primary={file.original_filename}
            secondary={
              <Box component="span" sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <span>{formatFileSize(file.file_size)}</span>
                {file.status === 'completed' && (
                  <>
                    <span>{file.email_count.toLocaleString()} emails</span>
                    <span>{file.attachment_count.toLocaleString()} attachments</span>
                  </>
                )}
                {isProcessing && file.emails_total && file.emails_total > 0 && (
                  <span>{file.email_count}/{file.emails_total} emails</span>
                )}
                <span>{formatRelativeTime(file.created_at)}</span>
              </Box>
            }
            primaryTypographyProps={{ noWrap: true }}
          />
          <Chip label={getStatusLabel()} color={getStatusColor()} size="small" sx={{ mr: 1 }} />
          <Tooltip title="Delete">
            <IconButton
              edge="end"
              onClick={() => setDeleteDialogOpen(true)}
              disabled={isProcessing}
            >
              <Delete />
            </IconButton>
          </Tooltip>
        </Box>

        {/* Progress bar for processing files */}
        {isProcessing && (
          <Box sx={{ width: '100%', mt: 1.5, px: 1 }}>
            {/* Stage indicators */}
            <Box sx={{ display: 'flex', gap: 0.5, mb: 1, flexWrap: 'wrap' }}>
              {PROCESSING_STAGES.slice(0, -1).map((stage) => {
                const isActive = file.current_phase === stage.key || file.status === stage.key;
                const isComplete = displayProgress > stage.progress[1];
                return (
                  <Chip
                    key={stage.key}
                    label={stage.label}
                    size="small"
                    color={isComplete ? 'success' : isActive ? 'primary' : 'default'}
                    variant={isActive ? 'filled' : 'outlined'}
                    sx={{
                      fontSize: '0.7rem',
                      height: 22,
                      opacity: isComplete || isActive ? 1 : 0.5,
                    }}
                  />
                );
              })}
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="caption" color="text.secondary">
                {taskProgress?.message || `${getStatusLabel()}...`}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {Math.round(displayProgress)}%
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={displayProgress}
              color="warning"
            />
          </Box>
        )}
      </ListItem>

      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Delete PST File?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete "{file.original_filename}"? This will remove all
            associated emails and attachments from the system. This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={() => {
              setDeleteDialogOpen(false);
              onDelete();
            }}
            color="error"
            variant="contained"
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

export function Upload() {
  const queryClient = useQueryClient();
  const [uploads, setUploads] = useState<UploadingFile[]>([]);
  const [showInfo, setShowInfo] = useState(true);

  const { data: pstFiles, isLoading: filesLoading } = useQuery({
    queryKey: ['pst-files'],
    queryFn: uploadApi.getPSTFiles,
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const CHUNK_SIZE = 95 * 1024 * 1024; // 95MB

      // Use standard upload for small files
      if (file.size <= CHUNK_SIZE) {
        return uploadApi.uploadPSTFile(file, (progress) => {
          setUploads((prev) =>
            prev.map((u) =>
              u.file === file ? { ...u, progress } : u
            )
          );
        });
      }

      // Chunked upload for large files
      const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
      const { upload_id } = await uploadApi.initChunkUpload(
        file.name,
        file.size,
        totalChunks
      );

      let uploadedBytes = 0;

      for (let i = 0; i < totalChunks; i++) {
        const start = i * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, file.size);
        const chunk = file.slice(start, end);

        await uploadApi.uploadChunk(upload_id, i, chunk, (chunkProgress) => {
          // Calculate total progress
          // chunkProgress is 0-100 for current chunk
          const chunkLoaded = (chunkProgress / 100) * chunk.size;
          const totalLoaded = uploadedBytes + chunkLoaded;
          const totalProgress = Math.min(Math.round((totalLoaded / file.size) * 100), 100);

          setUploads((prev) =>
            prev.map((u) =>
              u.file === file ? { ...u, progress: totalProgress } : u
            )
          );
        });

        uploadedBytes += chunk.size;
      }

      return uploadApi.completeChunkUpload(upload_id, file.name);
    },
    onSuccess: (_data, file) => {
      // Remove from active uploads list as it will now appear in the Uploaded Files list
      // (triggered by invalidateQueries below)
      setUploads((prev) => prev.filter((u) => u.file !== file));
      queryClient.invalidateQueries({ queryKey: ['pst-files'] });
      toast.success(`${file.name} uploaded successfully. Processing started.`);
    },
    onError: (error: Error, file) => {
      setUploads((prev) =>
        prev.map((u) =>
          u.file === file
            ? { ...u, status: 'failed', error: error.message }
            : u
        )
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: uploadApi.deletePSTFile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pst-files'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      toast.success('PST file deleted successfully');
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete file: ${error.message}`);
    },
  });

  const cancelMutation = useMutation({
    mutationFn: uploadApi.cancelTask,
    onSuccess: (_, taskId) => {
      setUploads((prev) =>
        prev.map((u) =>
          u.taskId === taskId
            ? { ...u, status: 'failed', error: 'Cancelled by user' }
            : u
        )
      );
      queryClient.invalidateQueries({ queryKey: ['pst-files'] });
      toast.success('Processing cancelled');
    },
  });

  const handleFilesSelected = useCallback(
    (files: File[]) => {
      // Add files to upload list
      const newUploads: UploadingFile[] = files.map((file) => ({
        file,
        progress: 0,
        status: 'uploading',
      }));

      setUploads((prev) => [...prev, ...newUploads]);

      // Start uploading each file
      files.forEach((file) => {
        uploadMutation.mutate(file);
      });
    },
    [uploadMutation]
  );

  const handleCancelUpload = useCallback(
    (upload: UploadingFile) => {
      if (upload.taskId) {
        cancelMutation.mutate(upload.taskId);
      } else {
        // Just remove from list if not yet processing
        setUploads((prev) => prev.filter((u) => u.file !== upload.file));
      }
    },
    [cancelMutation]
  );

  const clearCompletedUploads = useCallback(() => {
    setUploads((prev) =>
      prev.filter((u) => u.status === 'uploading' || u.status === 'processing')
    );
  }, []);

  const hasActiveUploads = uploads.some(
    (u) => u.status === 'uploading' || u.status === 'processing'
  );
  const hasCompletedUploads = uploads.some(
    (u) => u.status === 'completed' || u.status === 'failed'
  );

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Upload PST Files
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        Upload Outlook PST or OST files to analyze and search your emails.
      </Typography>

      <Collapse in={showInfo}>
        <Alert
          severity="info"
          icon={<Info />}
          onClose={() => setShowInfo(false)}
          sx={{ mb: 3 }}
        >
          <AlertTitle>How it works</AlertTitle>
          <Typography variant="body2">
            1. Upload your PST/OST file (up to 50GB)
            <br />
            2. The system extracts and indexes all emails and attachments
            <br />
            3. Search, browse, or chat with AI about your email content
          </Typography>
        </Alert>
      </Collapse>

      <Grid container spacing={3}>
        <Grid item xs={12} lg={7}>
          {/* Drop Zone */}
          <DropZone onFilesSelected={handleFilesSelected} disabled={hasActiveUploads} />

          {/* Active Uploads */}
          {uploads.length > 0 && (
            <Paper sx={{ mt: 3, p: 2 }}>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  mb: 2,
                }}
              >
                <Typography variant="h6">Upload Progress</Typography>
                {hasCompletedUploads && (
                  <Button size="small" onClick={clearCompletedUploads}>
                    Clear Completed
                  </Button>
                )}
              </Box>
              <List disablePadding>
                {uploads.map((upload, index) => (
                  <UploadProgressItem
                    key={`${upload.file.name}-${index}`}
                    upload={upload}
                    onCancel={() => handleCancelUpload(upload)}
                  />
                ))}
              </List>
            </Paper>
          )}
        </Grid>

        <Grid item xs={12} lg={5}>
          {/* Uploaded Files */}
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Uploaded Files
            </Typography>
            <Divider sx={{ mb: 2 }} />

            {filesLoading ? (
              <Box sx={{ py: 4, textAlign: 'center' }}>
                <Typography color="text.secondary">Loading files...</Typography>
              </Box>
            ) : !pstFiles || pstFiles.length === 0 ? (
              <Box sx={{ py: 4, textAlign: 'center' }}>
                <Folder sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
                <Typography color="text.secondary">
                  No files uploaded yet
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Upload a PST file to get started
                </Typography>
              </Box>
            ) : (
              <List disablePadding>
                {pstFiles.map((file) => (
                  <PSTFileItem
                    key={file.id}
                    file={file}
                    onDelete={() => deleteMutation.mutate(file.id)}
                  />
                ))}
              </List>
            )}
          </Paper>

          {/* File Details */}
          {pstFiles && pstFiles.length > 0 && (
            <Paper sx={{ p: 2, mt: 2 }}>
              <Typography variant="h6" gutterBottom>
                Storage Summary
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Total Files
                  </Typography>
                  <Typography variant="body2">{pstFiles.length}</Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Total Size
                  </Typography>
                  <Typography variant="body2">
                    {formatFileSize(pstFiles.reduce((acc, f) => acc + f.file_size, 0))}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Total Emails
                  </Typography>
                  <Typography variant="body2">
                    {pstFiles
                      .filter((f) => f.status === 'completed')
                      .reduce((acc, f) => acc + f.email_count, 0)
                      .toLocaleString()}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Total Attachments
                  </Typography>
                  <Typography variant="body2">
                    {pstFiles
                      .filter((f) => f.status === 'completed')
                      .reduce((acc, f) => acc + f.attachment_count, 0)
                      .toLocaleString()}
                  </Typography>
                </Box>
              </Box>
            </Paper>
          )}
        </Grid>
      </Grid>

      {/* Add keyframes for spinning animation */}
      <style>
        {`
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}
      </style>
    </Box>
  );
}
