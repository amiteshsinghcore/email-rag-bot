/**
 * Chat Page
 *
 * AI chat interface for email Q&A with streaming responses.
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Paper,
  TextField,
  Button,
  IconButton,
  CircularProgress,
  Divider,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Avatar,
  Chip,
  Collapse,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Tooltip,
  Alert,
  Grid,
} from '@mui/material';
import {
  Send,
  SmartToy,
  Person,
  Email as EmailIcon,
  ExpandMore,
  ExpandLess,
  Delete,
  Settings,
  Lightbulb,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ragApi, uploadApi } from '@/services/api';
import { formatRelativeTime } from '@/utils';
import type { ChatMessage, ChatRequest, Source } from '@/types';

interface Message extends ChatMessage {
  id: string;
  sources?: Source[];
  isStreaming?: boolean;
  error?: string;
  queryType?: string;
  modelUsed?: string;
}

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
  loading?: boolean;
}

function ChatInput({ value, onChange, onSend, disabled, loading }: ChatInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
      <TextField
        fullWidth
        multiline
        maxRows={4}
        placeholder="Ask a question about your emails..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled || loading}
        sx={{
          '& .MuiOutlinedInput-root': {
            bgcolor: 'background.paper',
          },
        }}
      />
      <Button
        variant="contained"
        onClick={onSend}
        disabled={disabled || loading || !value.trim()}
        sx={{ minWidth: 56, height: 56 }}
      >
        {loading ? <CircularProgress size={24} color="inherit" /> : <Send />}
      </Button>
    </Box>
  );
}

interface MessageBubbleProps {
  message: Message;
  onSourceClick: (emailId: string) => void;
}

function MessageBubble({ message, onSourceClick }: MessageBubbleProps) {
  const [showSources, setShowSources] = useState(false);
  const isUser = message.role === 'user';

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 2,
        mb: 3,
        flexDirection: isUser ? 'row-reverse' : 'row',
      }}
    >
      <Avatar
        sx={{
          bgcolor: isUser ? 'primary.main' : 'secondary.main',
          width: 40,
          height: 40,
        }}
      >
        {isUser ? <Person /> : <SmartToy />}
      </Avatar>

      <Box sx={{ flex: 1, maxWidth: '80%' }}>
        <Paper
          sx={{
            p: 2,
            bgcolor: isUser ? 'primary.main' : 'background.paper',
            color: isUser ? 'primary.contrastText' : 'text.primary',
            borderRadius: 2,
            borderTopRightRadius: isUser ? 0 : 2,
            borderTopLeftRadius: isUser ? 2 : 0,
          }}
        >
          {message.isStreaming && !message.content ? (
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              <CircularProgress size={8} sx={{ color: 'inherit' }} />
              <CircularProgress size={8} sx={{ color: 'inherit', animationDelay: '0.2s' }} />
              <CircularProgress size={8} sx={{ color: 'inherit', animationDelay: '0.4s' }} />
            </Box>
          ) : (
            <Typography
              variant="body1"
              sx={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                '& code': {
                  bgcolor: isUser ? 'rgba(255,255,255,0.2)' : 'action.hover',
                  px: 0.5,
                  borderRadius: 0.5,
                  fontFamily: 'monospace',
                },
              }}
            >
              {message.content}
              {message.isStreaming && (
                <Box
                  component="span"
                  sx={{
                    display: 'inline-block',
                    width: 8,
                    height: 16,
                    bgcolor: 'currentColor',
                    ml: 0.5,
                    animation: 'blink 1s infinite',
                    '@keyframes blink': {
                      '0%, 50%': { opacity: 1 },
                      '51%, 100%': { opacity: 0 },
                    },
                  }}
                />
              )}
            </Typography>
          )}

          {message.error && (
            <Alert severity="error" sx={{ mt: 1 }}>
              {message.error}
            </Alert>
          )}
        </Paper>

        {/* Metadata and sources for assistant messages */}
        {!isUser && !message.isStreaming && (
          <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
            {message.queryType && (
              <Chip
                label={message.queryType.replace('_', ' ')}
                size="small"
                variant="outlined"
              />
            )}
            {message.modelUsed && (
              <Typography variant="caption" color="text.secondary">
                {message.modelUsed}
              </Typography>
            )}

            {message.sources && message.sources.length > 0 && (
              <Button
                size="small"
                onClick={() => setShowSources(!showSources)}
                endIcon={showSources ? <ExpandLess /> : <ExpandMore />}
              >
                {message.sources.length} source{message.sources.length !== 1 ? 's' : ''}
              </Button>
            )}
          </Box>
        )}

        {/* Sources list */}
        {message.sources && message.sources.length > 0 && (
          <Collapse in={showSources}>
            <Paper sx={{ mt: 1, bgcolor: 'action.hover' }}>
              <List dense disablePadding>
                {message.sources.map((source, index) => (
                  <ListItemButton
                    key={`${source.email_id}-${index}`}
                    onClick={() => onSourceClick(source.email_id)}
                  >
                    <ListItemIcon sx={{ minWidth: 36 }}>
                      <EmailIcon fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={source.subject || '(No Subject)'}
                      secondary={
                        <Box component="span">
                          <Typography variant="caption" component="span">
                            {source.sender}
                          </Typography>
                          <Typography variant="caption" component="span" sx={{ ml: 1 }}>
                            {formatRelativeTime(source.date)}
                          </Typography>
                          <Typography
                            variant="caption"
                            component="span"
                            sx={{ ml: 1, color: 'primary.main' }}
                          >
                            {Math.round(source.relevance_score * 100)}% relevant
                          </Typography>
                        </Box>
                      }
                      primaryTypographyProps={{ noWrap: true, variant: 'body2' }}
                    />
                  </ListItemButton>
                ))}
              </List>
            </Paper>
          </Collapse>
        )}
      </Box>
    </Box>
  );
}

const EXAMPLE_QUESTIONS = [
  'What emails did I receive last week about the project?',
  'Summarize all communications with John Smith',
  'Find emails with attachments from the finance team',
  'What action items were mentioned in recent emails?',
  'Who has been emailing me the most?',
];

export function Chat() {
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(true);  // Show settings by default so users can select PST files

  // Settings
  const [selectedProvider, setSelectedProvider] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedPstFiles, setSelectedPstFiles] = useState<string[]>([]);

  // Fetch providers
  const { data: providersData } = useQuery({
    queryKey: ['rag-providers'],
    queryFn: ragApi.getProviders,
  });

  // Fetch PST files
  const { data: pstFiles = [] } = useQuery({
    queryKey: ['pst-files'],
    queryFn: uploadApi.getPSTFiles,
  });

  // Set default provider when loaded
  useEffect(() => {
    if (providersData && !selectedProvider) {
      setSelectedProvider(providersData.default_provider);
      const defaultProviderInfo = providersData.providers.find(
        (p) => p.name === providersData.default_provider
      );
      if (defaultProviderInfo) {
        setSelectedModel(defaultProviderInfo.default_model);
      }
    }
  }, [providersData, selectedProvider]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(async () => {
    const question = input.trim();
    if (!question || isLoading) return;

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: question,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    // Add assistant message placeholder
    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      isStreaming: true,
    };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      // Create abort controller for cancellation
      abortControllerRef.current = new AbortController();

      const request: ChatRequest = {
        question,
        chat_history: messages.map((m) => ({ role: m.role, content: m.content })),
        provider: selectedProvider || undefined,
        model: selectedModel || undefined,
        pst_file_ids: selectedPstFiles.length > 0 ? selectedPstFiles : undefined,
        stream: true,
        include_sources: true,
      };

      // Stream the response
      let fullContent = '';
      for await (const chunk of ragApi.chatStream(request)) {
        fullContent += chunk;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMessage.id ? { ...m, content: fullContent } : m
          )
        );
      }

      // After streaming, get the full response for metadata
      const fullResponse = await ragApi.chat({ ...request, stream: false });

      // Update with final metadata
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMessage.id
            ? {
                ...m,
                content: fullContent || fullResponse.answer,
                isStreaming: false,
                sources: fullResponse.sources,
                queryType: fullResponse.query_type,
                modelUsed: `${fullResponse.provider_used}/${fullResponse.model_used}`,
              }
            : m
        )
      );
    } catch (error) {
      // Update message with error
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMessage.id
            ? {
                ...m,
                isStreaming: false,
                error: error instanceof Error ? error.message : 'Failed to get response',
              }
            : m
        )
      );
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  }, [input, isLoading, messages, selectedProvider, selectedModel, selectedPstFiles]);

  const handleClear = useCallback(() => {
    setMessages([]);
  }, []);

  const handleSourceClick = useCallback(
    (emailId: string) => {
      navigate(`/emails/${emailId}`);
    },
    [navigate]
  );

  const handleExampleClick = useCallback((question: string) => {
    setInput(question);
  }, []);

  const availableProviders = providersData?.providers.filter((p) => p.is_available) || [];
  const currentProvider = availableProviders.find((p) => p.name === selectedProvider);
  const completedPstFiles = pstFiles.filter((f) => f.status === 'completed');

  return (
    <Box sx={{ height: 'calc(100vh - 180px)', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            Chat with AI
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Ask questions about your emails using natural language.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Clear chat">
            <IconButton onClick={handleClear} disabled={messages.length === 0}>
              <Delete />
            </IconButton>
          </Tooltip>
          <Tooltip title="Settings">
            <IconButton onClick={() => setShowSettings(!showSettings)}>
              <Settings />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Settings Panel */}
      <Collapse in={showSettings}>
        <Paper sx={{ p: 2, mb: 2 }}>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth size="small">
                <InputLabel>LLM Provider</InputLabel>
                <Select
                  value={selectedProvider}
                  onChange={(e) => {
                    setSelectedProvider(e.target.value);
                    const provider = availableProviders.find((p) => p.name === e.target.value);
                    if (provider) {
                      setSelectedModel(provider.default_model);
                    }
                  }}
                  label="LLM Provider"
                >
                  {availableProviders.map((provider) => (
                    <MenuItem key={provider.name} value={provider.name}>
                      {provider.display_name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth size="small">
                <InputLabel>Model</InputLabel>
                <Select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  label="Model"
                  disabled={!currentProvider}
                >
                  {currentProvider?.models.map((model) => (
                    <MenuItem key={model} value={model}>
                      {model}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth size="small">
                <InputLabel>PST Files</InputLabel>
                <Select
                  multiple
                  value={selectedPstFiles}
                  onChange={(e) => setSelectedPstFiles(e.target.value as string[])}
                  label="PST Files"
                  renderValue={(selected) =>
                    selected.length === 0 ? 'All files' : `${selected.length} selected`
                  }
                >
                  {completedPstFiles.map((file) => (
                    <MenuItem key={file.id} value={file.id}>
                      {file.original_filename}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </Paper>
      </Collapse>

      {/* Messages Area */}
      <Paper
        sx={{
          flex: 1,
          overflow: 'auto',
          p: 3,
          mb: 2,
          bgcolor: 'background.default',
        }}
      >
        {messages.length === 0 ? (
          <Box
            sx={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              gap: 3,
            }}
          >
            <SmartToy sx={{ fontSize: 64, color: 'text.secondary' }} />
            <Typography variant="h6" color="text.secondary">
              Start a conversation
            </Typography>
            <Typography variant="body2" color="text.secondary" textAlign="center">
              Ask questions about your emails. I can help you find information,
              summarize conversations, and more.
            </Typography>

            <Divider sx={{ width: '100%', maxWidth: 400, my: 2 }}>
              <Chip icon={<Lightbulb />} label="Try asking" size="small" />
            </Divider>

            <Box
              sx={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 1,
                justifyContent: 'center',
                maxWidth: 600,
              }}
            >
              {EXAMPLE_QUESTIONS.map((question, index) => (
                <Chip
                  key={index}
                  label={question}
                  onClick={() => handleExampleClick(question)}
                  variant="outlined"
                  sx={{ cursor: 'pointer' }}
                />
              ))}
            </Box>
          </Box>
        ) : (
          <>
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                onSourceClick={handleSourceClick}
              />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </Paper>

      {/* Input Area */}
      <ChatInput
        value={input}
        onChange={setInput}
        onSend={handleSend}
        disabled={completedPstFiles.length === 0}
        loading={isLoading}
      />

      {completedPstFiles.length === 0 && (
        <Alert severity="warning" sx={{ mt: 2 }}>
          No emails available. Please upload and process a PST file first.
        </Alert>
      )}
    </Box>
  );
}
