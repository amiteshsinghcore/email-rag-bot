/**
 * Email View Page
 *
 * Full email viewer with attachments and thread view.
 */

import { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  IconButton,
  Skeleton,
  Alert,
  Tabs,
  Tab,
  Tooltip,
  Avatar,
  Grid,
  Collapse,
} from '@mui/material';
import {
  ArrowBack,
  AttachFile,
  Download,
  Email as EmailIcon,
  Schedule,
  Print,
  ExpandMore,
  ExpandLess,
  PriorityHigh,
  ContentCopy,
  Description,
  Image,
  PictureAsPdf,
  InsertDriveFile,
} from '@mui/icons-material';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { emailsApi } from '@/services/api';
import { formatDateTime, formatFileSize, getInitials, downloadBlob, copyToClipboard } from '@/utils';
import type { Email, Attachment, EmailSummary } from '@/types';

interface EmailHeaderProps {
  email: Email;
  onBack: () => void;
}

function EmailHeader({ email, onBack }: EmailHeaderProps) {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
        <IconButton onClick={onBack} sx={{ mt: -0.5 }}>
          <ArrowBack />
        </IconButton>

        <Avatar
          sx={{
            width: 48,
            height: 48,
            bgcolor: 'primary.main',
          }}
        >
          {getInitials(email.sender_name || email.sender)}
        </Avatar>

        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <Typography variant="h6" noWrap>
              {email.subject || '(No Subject)'}
            </Typography>
            {email.importance === 'high' && (
              <Tooltip title="High importance">
                <PriorityHigh color="error" />
              </Tooltip>
            )}
            {email.has_attachments && (
              <Chip
                icon={<AttachFile />}
                label={`${email.attachment_count} attachment${email.attachment_count !== 1 ? 's' : ''}`}
                size="small"
                variant="outlined"
              />
            )}
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
            <Typography variant="body2" fontWeight={500}>
              {email.sender_name || email.sender}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              &lt;{email.sender}&gt;
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
            <Schedule fontSize="small" color="action" />
            <Typography variant="body2" color="text.secondary">
              {formatDateTime(email.date_sent)}
            </Typography>
          </Box>

          <Button
            size="small"
            onClick={() => setShowDetails(!showDetails)}
            endIcon={showDetails ? <ExpandLess /> : <ExpandMore />}
            sx={{ mt: 1 }}
          >
            {showDetails ? 'Hide details' : 'Show details'}
          </Button>

          <Collapse in={showDetails}>
            <Box sx={{ mt: 2, bgcolor: 'action.hover', p: 2, borderRadius: 1 }}>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    From
                  </Typography>
                  <Typography variant="body2">
                    {email.sender_name ? `${email.sender_name} <${email.sender}>` : email.sender}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Date
                  </Typography>
                  <Typography variant="body2">
                    {formatDateTime(email.date_sent)}
                  </Typography>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="caption" color="text.secondary" display="block">
                    To
                  </Typography>
                  <Typography variant="body2">
                    {email.recipients.join(', ') || 'Unknown'}
                  </Typography>
                </Grid>
                {email.cc.length > 0 && (
                  <Grid item xs={12}>
                    <Typography variant="caption" color="text.secondary" display="block">
                      CC
                    </Typography>
                    <Typography variant="body2">{email.cc.join(', ')}</Typography>
                  </Grid>
                )}
                {email.bcc.length > 0 && (
                  <Grid item xs={12}>
                    <Typography variant="caption" color="text.secondary" display="block">
                      BCC
                    </Typography>
                    <Typography variant="body2">{email.bcc.join(', ')}</Typography>
                  </Grid>
                )}
              </Grid>
            </Box>
          </Collapse>
        </Box>

        {/* Actions */}
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Copy email address">
            <IconButton
              size="small"
              onClick={async () => {
                const success = await copyToClipboard(email.sender);
                if (success) {
                  toast.success('Email copied to clipboard');
                }
              }}
            >
              <ContentCopy fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Print">
            <IconButton size="small" onClick={() => window.print()}>
              <Print fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
    </Paper>
  );
}

interface EmailBodyProps {
  email: Email;
}

/**
 * Sanitize email HTML to remove/replace problematic elements:
 * - cid: URLs (Content-ID references to embedded images that can't be loaded)
 * - Potentially dangerous scripts or iframes
 */
function sanitizeEmailHtml(html: string): string {
  if (!html) return '';

  let sanitized = html;

  // Replace cid: image sources with a placeholder or remove them
  // cid:image001.png@01DC80B8.CECF4460 -> inline broken image indicator
  sanitized = sanitized.replace(
    /src=["']cid:[^"']+["']/gi,
    'src="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'100\' height=\'100\' viewBox=\'0 0 100 100\'%3E%3Crect fill=\'%23f0f0f0\' width=\'100\' height=\'100\'/%3E%3Ctext x=\'50\' y=\'50\' font-size=\'10\' text-anchor=\'middle\' dy=\'.3em\' fill=\'%23999\'%3EEmbedded Image%3C/text%3E%3C/svg%3E" alt="[Embedded Image]"'
  );

  // Remove script tags (basic XSS protection)
  sanitized = sanitized.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');

  // Remove onclick and other event handlers
  sanitized = sanitized.replace(/\s+on\w+="[^"]*"/gi, '');
  sanitized = sanitized.replace(/\s+on\w+='[^']*'/gi, '');

  return sanitized;
}

function EmailBody({ email }: EmailBodyProps) {
  const [viewMode, setViewMode] = useState<'text' | 'html'>(
    email.body_html ? 'html' : 'text'
  );

  // Sanitize HTML content to remove cid: URLs and other problematic content
  const sanitizedHtml = email.body_html ? sanitizeEmailHtml(email.body_html) : '';

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="subtitle1">Message</Typography>
        {email.body_html && email.body_text && (
          <Tabs
            value={viewMode}
            onChange={(_, v) => setViewMode(v)}
            sx={{ minHeight: 36 }}
          >
            <Tab label="HTML" value="html" sx={{ minHeight: 36, py: 0 }} />
            <Tab label="Text" value="text" sx={{ minHeight: 36, py: 0 }} />
          </Tabs>
        )}
      </Box>

      <Divider sx={{ mb: 2 }} />

      {viewMode === 'html' && sanitizedHtml ? (
        <Box
          sx={{
            '& img': { maxWidth: '100%' },
            '& a': { color: 'primary.main' },
            '& table': { borderCollapse: 'collapse' },
            '& td, & th': { border: '1px solid', borderColor: 'divider', p: 1 },
          }}
          dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
        />
      ) : (
        <Typography
          variant="body1"
          component="pre"
          sx={{
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontFamily: 'inherit',
            m: 0,
          }}
        >
          {email.body_text || '(No message content)'}
        </Typography>
      )}
    </Paper>
  );
}

interface AttachmentListProps {
  emailId: string;
  attachments: Attachment[];
}

function AttachmentList({ emailId, attachments }: AttachmentListProps) {
  const downloadMutation = useMutation({
    mutationFn: async (attachment: Attachment) => {
      const blob = await emailsApi.downloadAttachment(emailId, attachment.id);
      downloadBlob(blob, attachment.filename);
    },
    onSuccess: (_, attachment) => {
      toast.success(`Downloaded ${attachment.filename}`);
    },
    onError: (error: Error, attachment) => {
      toast.error(`Failed to download ${attachment.filename}: ${error.message}`);
    },
  });

  const getFileIcon = (contentType: string, filename: string) => {
    const lowerFilename = filename.toLowerCase();

    if (contentType.startsWith('image/') || /\.(jpg|jpeg|png|gif|webp|svg)$/.test(lowerFilename)) {
      return <Image color="primary" />;
    }
    if (contentType === 'application/pdf' || lowerFilename.endsWith('.pdf')) {
      return <PictureAsPdf color="error" />;
    }
    if (
      contentType.includes('word') ||
      contentType.includes('document') ||
      /\.(doc|docx|odt)$/.test(lowerFilename)
    ) {
      return <Description color="primary" />;
    }
    return <InsertDriveFile color="action" />;
  };

  if (attachments.length === 0) {
    return null;
  }

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="subtitle1" gutterBottom>
        Attachments ({attachments.length})
      </Typography>
      <Divider sx={{ mb: 2 }} />
      <List disablePadding>
        {attachments.map((attachment) => (
          <ListItem
            key={attachment.id}
            disablePadding
            sx={{
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              mb: 1,
            }}
            secondaryAction={
              <IconButton
                edge="end"
                onClick={() => downloadMutation.mutate(attachment)}
                disabled={downloadMutation.isPending}
              >
                <Download />
              </IconButton>
            }
          >
            <ListItemButton
              onClick={() => downloadMutation.mutate(attachment)}
              disabled={downloadMutation.isPending}
            >
              <ListItemIcon>
                {getFileIcon(attachment.content_type, attachment.filename)}
              </ListItemIcon>
              <ListItemText
                primary={attachment.filename}
                secondary={formatFileSize(attachment.size)}
              />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Paper>
  );
}

interface ThreadViewProps {
  thread: EmailSummary[];
  currentEmailId: string;
  onEmailClick: (emailId: string) => void;
}

function ThreadView({ thread, currentEmailId, onEmailClick }: ThreadViewProps) {
  if (thread.length <= 1) {
    return null;
  }

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="subtitle1" gutterBottom>
        Conversation Thread ({thread.length} emails)
      </Typography>
      <Divider sx={{ mb: 2 }} />
      <List disablePadding>
        {thread.map((email) => (
          <ListItemButton
            key={email.id}
            onClick={() => onEmailClick(email.id)}
            selected={email.id === currentEmailId}
            sx={{
              borderRadius: 1,
              mb: 1,
              border: '1px solid',
              borderColor: email.id === currentEmailId ? 'primary.main' : 'divider',
            }}
          >
            <ListItemIcon>
              <EmailIcon color={email.id === currentEmailId ? 'primary' : 'action'} />
            </ListItemIcon>
            <ListItemText
              primary={email.subject || '(No Subject)'}
              secondary={
                <Box component="span">
                  <Typography variant="caption" component="span">
                    {email.sender_name || email.sender}
                  </Typography>
                  <Typography variant="caption" component="span" sx={{ ml: 1 }}>
                    {formatDateTime(email.date_sent)}
                  </Typography>
                </Box>
              }
              primaryTypographyProps={{ noWrap: true }}
            />
          </ListItemButton>
        ))}
      </List>
    </Paper>
  );
}

export function EmailView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Fetch email details
  const {
    data: email,
    isLoading: emailLoading,
    error: emailError,
  } = useQuery({
    queryKey: ['email', id],
    queryFn: () => emailsApi.getEmail(id!),
    enabled: !!id,
  });

  // Fetch attachments
  const { data: attachments = [] } = useQuery({
    queryKey: ['email-attachments', id],
    queryFn: () => emailsApi.getEmailAttachments(id!),
    enabled: !!id && email?.has_attachments,
  });

  // Fetch thread
  const { data: thread = [] } = useQuery({
    queryKey: ['email-thread', email?.conversation_id],
    queryFn: () => emailsApi.getThread(email!.conversation_id!),
    enabled: !!email?.conversation_id,
  });

  const handleBack = () => {
    navigate(-1);
  };

  const handleEmailClick = (emailId: string) => {
    navigate(`/emails/${emailId}`);
  };

  if (emailLoading) {
    return (
      <Box>
        <Paper sx={{ p: 3, mb: 3 }}>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Skeleton variant="circular" width={48} height={48} />
            <Box sx={{ flex: 1 }}>
              <Skeleton variant="text" width="60%" height={32} />
              <Skeleton variant="text" width="40%" />
              <Skeleton variant="text" width="30%" />
            </Box>
          </Box>
        </Paper>
        <Paper sx={{ p: 3 }}>
          <Skeleton variant="rectangular" height={300} />
        </Paper>
      </Box>
    );
  }

  if (emailError || !email) {
    return (
      <Box>
        <Button startIcon={<ArrowBack />} onClick={handleBack} sx={{ mb: 2 }}>
          Back
        </Button>
        <Alert severity="error">
          {emailError instanceof Error
            ? emailError.message
            : 'Failed to load email. Please try again.'}
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Grid container spacing={3}>
        <Grid item xs={12} lg={thread.length > 1 ? 8 : 12}>
          <EmailHeader email={email} onBack={handleBack} />
          <AttachmentList emailId={id!} attachments={attachments} />
          <EmailBody email={email} />
        </Grid>

        {thread.length > 1 && (
          <Grid item xs={12} lg={4}>
            <ThreadView
              thread={thread}
              currentEmailId={id!}
              onEmailClick={handleEmailClick}
            />
          </Grid>
        )}
      </Grid>
    </Box>
  );
}
