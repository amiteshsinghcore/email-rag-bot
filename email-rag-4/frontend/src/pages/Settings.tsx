/**
 * Settings Page
 *
 * User settings, preferences, and LLM provider configuration with API key testing.
 */

import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  TextField,
  Button,
  Alert,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  IconButton,
  Skeleton,
  Collapse,
  Card,
  CardContent,
  CardActions,
  InputAdornment,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Divider,
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  Save,
  Person,
  Key,
  SmartToy,
  CheckCircle,
  Error as ErrorIcon,
  Visibility,
  VisibilityOff,
  Refresh,
  Info,
  ExpandMore,
  ExpandLess,
  PlayArrow,
  Settings as SettingsIcon,
  Edit,
  Add,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { ragApi, usersApi } from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import type { LLMProvider, LLMSettingsResponse, User } from '@/types';

// Provider display names and models
const PROVIDER_INFO: Record<string, { displayName: string; models: string[] }> = {
  openai: {
    displayName: 'OpenAI',
    models: ['gpt-4-turbo-preview', 'gpt-4', 'gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
  },
  anthropic: {
    displayName: 'Anthropic',
    models: ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
  },
  google: {
    displayName: 'Google',
    models: ['gemini-pro', 'gemini-1.5-pro', 'gemini-1.5-flash'],
  },
  xai: {
    displayName: 'xAI',
    models: ['grok-beta', 'grok-2'],
  },
  groq: {
    displayName: 'Groq',
    models: ['llama-3.3-70b-versatile', 'llama-3.1-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768', 'gemma2-9b-it'],
  },
  cerebras: {
    displayName: 'Cerebras',
    models: ['llama-3.3-70b', 'llama3.1-70b', 'llama3.1-8b'],
  },
  custom: {
    displayName: 'Custom',
    models: [],
  },
};

interface ApiKeyTestDialogProps {
  open: boolean;
  onClose: () => void;
}

function ApiKeyTestDialog({ open, onClose }: ApiKeyTestDialogProps) {
  const [provider, setProvider] = useState('groq');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [showKey, setShowKey] = useState(false);

  const testMutation = useMutation({
    mutationFn: ragApi.testApiKey,
    onSuccess: (data) => {
      if (data.success) {
        toast.success(`API key is valid! ${data.message}`);
      } else {
        toast.error(`API key test failed: ${data.error || data.message}`);
      }
    },
    onError: (error: Error) => {
      toast.error(`Test failed: ${error.message}`);
    },
  });

  const handleTest = () => {
    if (!apiKey.trim()) {
      toast.error('Please enter an API key');
      return;
    }
    testMutation.mutate({
      provider,
      api_key: apiKey,
      model: model || undefined,
      base_url: provider === 'custom' ? baseUrl : undefined,
    });
  };

  const handleClose = () => {
    setApiKey('');
    setModel('');
    setBaseUrl('');
    setShowKey(false);
    onClose();
  };

  const providerModels = PROVIDER_INFO[provider]?.models || [];

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SettingsIcon color="primary" />
          Test LLM API Key
        </Box>
      </DialogTitle>
      <DialogContent>
        <Alert severity="info" sx={{ mb: 3, mt: 1 }}>
          Test your API key before saving it. This makes a simple test request to verify connectivity.
        </Alert>

        <FormControl fullWidth sx={{ mb: 2 }}>
          <InputLabel>Provider</InputLabel>
          <Select
            value={provider}
            label="Provider"
            onChange={(e) => {
              setProvider(e.target.value);
              setModel('');
            }}
          >
            {Object.entries(PROVIDER_INFO).map(([key, info]) => (
              <MenuItem key={key} value={key}>
                {info.displayName}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <TextField
          fullWidth
          label="API Key"
          type={showKey ? 'text' : 'password'}
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          sx={{ mb: 2 }}
          placeholder={
            provider === 'openai'
              ? 'sk-...'
              : provider === 'anthropic'
              ? 'sk-ant-...'
              : provider === 'groq'
              ? 'gsk_...'
              : 'Enter your API key'
          }
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton onClick={() => setShowKey(!showKey)}>
                  {showKey ? <VisibilityOff /> : <Visibility />}
                </IconButton>
              </InputAdornment>
            ),
          }}
        />

        {providerModels.length > 0 && (
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Model (Optional)</InputLabel>
            <Select
              value={model}
              label="Model (Optional)"
              onChange={(e) => setModel(e.target.value)}
            >
              <MenuItem value="">Default</MenuItem>
              {providerModels.map((m) => (
                <MenuItem key={m} value={m}>
                  {m}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}

        {provider === 'custom' && (
          <TextField
            fullWidth
            label="Base URL"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            sx={{ mb: 2 }}
            placeholder="https://your-llm-endpoint.com/v1"
          />
        )}

        {testMutation.data && (
          <Alert
            severity={testMutation.data.success ? 'success' : 'error'}
            sx={{ mt: 2 }}
          >
            <Typography variant="subtitle2">
              {testMutation.data.success ? 'Success!' : 'Failed'}
            </Typography>
            <Typography variant="body2">{testMutation.data.message}</Typography>
            {testMutation.data.model && (
              <Typography variant="body2">Model: {testMutation.data.model}</Typography>
            )}
            {testMutation.data.error && (
              <Typography variant="body2" color="error">
                Error: {testMutation.data.error}
              </Typography>
            )}
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Close</Button>
        <Button
          variant="contained"
          onClick={handleTest}
          disabled={testMutation.isPending || !apiKey.trim()}
          startIcon={testMutation.isPending ? <CircularProgress size={20} /> : <PlayArrow />}
        >
          {testMutation.isPending ? 'Testing...' : 'Test Connection'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// Provider Configuration Dialog
interface ProviderConfigDialogProps {
  open: boolean;
  onClose: () => void;
  provider: string | null;
  existingSettings?: LLMSettingsResponse | null;
  onSave: () => void;
}

function ProviderConfigDialog({
  open,
  onClose,
  provider,
  existingSettings,
  onSave,
}: ProviderConfigDialogProps) {
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [isEnabled, setIsEnabled] = useState(true);
  const [isDefault, setIsDefault] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [customModels, setCustomModels] = useState<string[]>([]);
  const [loadingCustomModels, setLoadingCustomModels] = useState(false);
  const [customModelsError, setCustomModelsError] = useState<string | null>(null);

  const fetchCustomModels = async (url?: string, key?: string) => {
    setLoadingCustomModels(true);
    setCustomModelsError(null);
    try {
      const result = await ragApi.fetchCustomModels({
        base_url: url || baseUrl || undefined,
        api_key: key || apiKey || undefined,
      });
      if (result.success) {
        setCustomModels(result.models);
        if (result.models.length === 0) {
          setCustomModelsError('No models found at endpoint');
        }
      } else {
        setCustomModelsError(result.error || 'Failed to fetch models');
        setCustomModels([]);
      }
    } catch (error) {
      setCustomModelsError('Failed to connect to endpoint');
      setCustomModels([]);
    } finally {
      setLoadingCustomModels(false);
    }
  };

  useEffect(() => {
    if (open && existingSettings) {
      setApiKey(''); // Never pre-fill API key for security
      setModel(existingSettings.model || '');
      setBaseUrl(existingSettings.base_url || '');
      setIsEnabled(existingSettings.is_enabled);
      setIsDefault(existingSettings.is_default);
      // Fetch custom models if provider is custom and base_url exists
      if (provider === 'custom' && existingSettings.base_url) {
        fetchCustomModels(existingSettings.base_url);
      }
    } else if (open) {
      setApiKey('');
      setModel('');
      setBaseUrl('');
      setIsEnabled(true);
      setIsDefault(false);
      setCustomModels([]);
      setCustomModelsError(null);
      // Try to fetch custom models with saved settings
      if (provider === 'custom') {
        fetchCustomModels();
      }
    }
  }, [open, existingSettings, provider]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!provider) throw new Error('No provider selected');
      return ragApi.createOrUpdateLLMSettings({
        provider,
        api_key: apiKey || undefined,
        model: model || undefined,
        base_url: baseUrl || undefined,
        is_enabled: isEnabled,
        is_default: isDefault,
      });
    },
    onSuccess: () => {
      toast.success(`${PROVIDER_INFO[provider || '']?.displayName || provider} settings saved`);
      onSave();
      handleClose();
    },
    onError: (error: Error) => {
      toast.error(`Failed to save settings: ${error.message}`);
    },
  });

  const testMutation = useMutation({
    mutationFn: () => {
      if (!provider) throw new Error('No provider selected');
      if (!apiKey.trim()) throw new Error('API key is required for testing');
      return ragApi.testApiKey({
        provider,
        api_key: apiKey,
        model: model || undefined,
        base_url: provider === 'custom' ? baseUrl : undefined,
      });
    },
    onSuccess: (data) => {
      if (data.success) {
        toast.success('API key verified successfully!');
      } else {
        toast.error(`API key test failed: ${data.error || data.message}`);
      }
    },
    onError: (error: Error) => {
      toast.error(`Test failed: ${error.message}`);
    },
  });

  const handleClose = () => {
    setApiKey('');
    setModel('');
    setBaseUrl('');
    setShowKey(false);
    onClose();
  };

  const providerModels = PROVIDER_INFO[provider || '']?.models || [];
  const providerDisplayName = PROVIDER_INFO[provider || '']?.displayName || provider;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SmartToy color="primary" />
          Configure {providerDisplayName}
        </Box>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 1 }}>
          {existingSettings?.api_key_set && (
            <Alert severity="info" sx={{ mb: 2 }}>
              API key is already configured. Leave the field empty to keep the existing key, or enter a new one to replace it.
              <br />
              <Typography variant="caption" component="span">
                Current key: {existingSettings.api_key_preview}
              </Typography>
            </Alert>
          )}

          <TextField
            fullWidth
            label="API Key"
            type={showKey ? 'text' : 'password'}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            sx={{ mb: 2 }}
            placeholder={existingSettings?.api_key_set ? 'Leave empty to keep existing key' : 'Enter API key'}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton onClick={() => setShowKey(!showKey)}>
                    {showKey ? <VisibilityOff /> : <Visibility />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />

          {provider === 'custom' && (
            <TextField
              fullWidth
              label="Base URL"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              sx={{ mb: 2 }}
              placeholder="https://your-llm-endpoint.com/v1"
              helperText="OpenAI-compatible API endpoint"
            />
          )}

          {provider === 'custom' ? (
            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                {customModels.length > 0 ? (
                  <FormControl fullWidth>
                    <InputLabel>Model</InputLabel>
                    <Select
                      value={model}
                      label="Model"
                      onChange={(e) => setModel(e.target.value)}
                    >
                      {customModels.map((m) => (
                        <MenuItem key={m} value={m}>
                          {m}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                ) : (
                  <TextField
                    fullWidth
                    label="Model"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="Enter model name or fetch from endpoint"
                    error={!!customModelsError}
                    helperText={customModelsError}
                  />
                )}
                <Tooltip title="Fetch available models from endpoint">
                  <IconButton
                    onClick={() => fetchCustomModels(baseUrl, apiKey)}
                    disabled={loadingCustomModels}
                    sx={{ mt: 1 }}
                  >
                    {loadingCustomModels ? <CircularProgress size={24} /> : <Refresh />}
                  </IconButton>
                </Tooltip>
              </Box>
              {customModels.length > 0 && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                  {customModels.length} model(s) available from endpoint
                </Typography>
              )}
            </Box>
          ) : providerModels.length > 0 ? (
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Model</InputLabel>
              <Select
                value={model}
                label="Model"
                onChange={(e) => setModel(e.target.value)}
              >
                <MenuItem value="">Default</MenuItem>
                {providerModels.map((m) => (
                  <MenuItem key={m} value={m}>
                    {m}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          ) : (
            <TextField
              fullWidth
              label="Model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              sx={{ mb: 2 }}
              placeholder="Enter model name"
            />
          )}

          <Divider sx={{ my: 2 }} />

          <FormControlLabel
            control={
              <Switch
                checked={isEnabled}
                onChange={(e) => setIsEnabled(e.target.checked)}
              />
            }
            label="Enable this provider"
          />

          <FormControlLabel
            control={
              <Switch
                checked={isDefault}
                onChange={(e) => setIsDefault(e.target.checked)}
              />
            }
            label="Set as default provider"
          />

          {testMutation.data && (
            <Alert
              severity={testMutation.data.success ? 'success' : 'error'}
              sx={{ mt: 2 }}
            >
              {testMutation.data.success
                ? `Verified! Model: ${testMutation.data.model}`
                : testMutation.data.error || 'Test failed'}
            </Alert>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          onClick={() => testMutation.mutate()}
          disabled={testMutation.isPending || !apiKey.trim()}
          startIcon={testMutation.isPending ? <CircularProgress size={16} /> : <PlayArrow />}
        >
          Test
        </Button>
        <Button
          variant="contained"
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          startIcon={saveMutation.isPending ? <CircularProgress size={16} /> : <Save />}
        >
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}

interface ProviderCardProps {
  provider: LLMProvider;
  settings?: LLMSettingsResponse | null;
  isDefault: boolean;
  onConfigure: () => void;
  onSetDefault: () => void;
}

function ProviderCard({ provider, settings, isDefault, onConfigure, onSetDefault }: ProviderCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card
      sx={{
        border: '1px solid',
        borderColor: isDefault ? 'primary.main' : 'divider',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <CardContent sx={{ flexGrow: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <SmartToy color={provider.is_available ? 'primary' : 'disabled'} />
            <Typography variant="h6">{provider.display_name}</Typography>
            {isDefault && (
              <Chip label="Default" size="small" color="primary" />
            )}
          </Box>
          <Chip
            icon={provider.is_available ? <CheckCircle /> : <ErrorIcon />}
            label={provider.is_available ? 'Available' : 'Not Configured'}
            size="small"
            color={provider.is_available ? 'success' : 'default'}
            variant="outlined"
          />
        </Box>

        {settings?.api_key_set && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            API Key: {settings.api_key_preview}
          </Typography>
        )}

        {settings?.model && (
          <Typography variant="body2" color="text.secondary">
            Model: {settings.model}
          </Typography>
        )}

        {settings?.base_url && (
          <Typography variant="body2" color="text.secondary" sx={{ wordBreak: 'break-all' }}>
            Endpoint: {settings.base_url}
          </Typography>
        )}

        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {provider.models.length} model{provider.models.length !== 1 ? 's' : ''} supported
        </Typography>

        <Button
          size="small"
          onClick={() => setExpanded(!expanded)}
          endIcon={expanded ? <ExpandLess /> : <ExpandMore />}
          sx={{ mt: 1 }}
        >
          {expanded ? 'Hide models' : 'Show models'}
        </Button>

        <Collapse in={expanded}>
          <Box sx={{ mt: 2 }}>
            <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
              Available Models:
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
              {provider.models.map((model) => (
                <Chip
                  key={model}
                  label={model}
                  size="small"
                  variant={model === provider.default_model ? 'filled' : 'outlined'}
                  color={model === provider.default_model ? 'primary' : 'default'}
                />
              ))}
            </Box>
          </Box>
        </Collapse>
      </CardContent>

      <CardActions sx={{ justifyContent: 'flex-end' }}>
        <Button
          size="small"
          startIcon={settings ? <Edit /> : <Add />}
          onClick={onConfigure}
        >
          {settings ? 'Configure' : 'Set Up'}
        </Button>
        {!isDefault && provider.is_available && (
          <Button size="small" onClick={onSetDefault}>
            Set as Default
          </Button>
        )}
      </CardActions>
    </Card>
  );
}

interface ProfileSectionProps {
  user: User;
  onUpdate: (data: Partial<User>) => void;
  isUpdating: boolean;
}

function ProfileSection({ user, onUpdate, isUpdating }: ProfileSectionProps) {
  const [fullName, setFullName] = useState(user.full_name);
  const [email, setEmail] = useState(user.email);

  const handleSave = () => {
    if (fullName !== user.full_name || email !== user.email) {
      onUpdate({ full_name: fullName, email });
    }
  };

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
        <Person color="primary" />
        <Typography variant="h6">Profile</Typography>
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Full Name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Role"
            value={user.role}
            disabled
            InputProps={{
              readOnly: true,
            }}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Member Since"
            value={new Date(user.created_at).toLocaleDateString()}
            disabled
            InputProps={{
              readOnly: true,
            }}
          />
        </Grid>
      </Grid>

      <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
        <Button
          variant="contained"
          startIcon={<Save />}
          onClick={handleSave}
          disabled={isUpdating || (fullName === user.full_name && email === user.email)}
        >
          {isUpdating ? 'Saving...' : 'Save Changes'}
        </Button>
      </Box>
    </Paper>
  );
}

interface PasswordSectionProps {
  onChangePassword: (currentPassword: string, newPassword: string) => void;
  isChanging: boolean;
}

function PasswordSection({ onChangePassword, isChanging }: PasswordSectionProps) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPasswords, setShowPasswords] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = () => {
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    setError('');
    onChangePassword(currentPassword, newPassword);
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
  };

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
        <Key color="primary" />
        <Typography variant="h6">Change Password</Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Current Password"
            type={showPasswords ? 'text' : 'password'}
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton onClick={() => setShowPasswords(!showPasswords)}>
                    {showPasswords ? <VisibilityOff /> : <Visibility />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="New Password"
            type={showPasswords ? 'text' : 'password'}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Confirm New Password"
            type={showPasswords ? 'text' : 'password'}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            error={confirmPassword !== '' && confirmPassword !== newPassword}
            helperText={
              confirmPassword !== '' && confirmPassword !== newPassword
                ? 'Passwords do not match'
                : ''
            }
          />
        </Grid>
      </Grid>

      <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
        <Button
          variant="contained"
          startIcon={<Key />}
          onClick={handleSubmit}
          disabled={isChanging || !currentPassword || !newPassword || !confirmPassword}
        >
          {isChanging ? 'Changing...' : 'Change Password'}
        </Button>
      </Box>
    </Paper>
  );
}

export function Settings() {
  const { user, updateUser } = useAuthStore();
  const queryClient = useQueryClient();
  const [testDialogOpen, setTestDialogOpen] = useState(false);
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);

  // Fetch providers
  const {
    data: providersData,
    isLoading: providersLoading,
    refetch: refetchProviders,
  } = useQuery({
    queryKey: ['rag-providers'],
    queryFn: ragApi.getProviders,
  });

  // Fetch LLM settings - available for all authenticated users
  const {
    data: llmSettingsData,
    isLoading: settingsLoading,
    refetch: refetchSettings,
  } = useQuery({
    queryKey: ['llm-settings'],
    queryFn: ragApi.getLLMSettings,
  });

  // Fetch health check
  const { data: healthData, refetch: refetchHealth } = useQuery({
    queryKey: ['rag-health'],
    queryFn: ragApi.healthCheck,
    refetchInterval: 60000, // Check every minute
  });

  // Update user mutation
  const updateUserMutation = useMutation({
    mutationFn: async (data: Partial<User>) => {
      if (!user) throw new Error('Not logged in');
      return usersApi.updateUser(user.id, data);
    },
    onSuccess: (updatedUser) => {
      updateUser(updatedUser);
      toast.success('Profile updated successfully');
    },
    onError: (error: Error) => {
      toast.error(`Failed to update profile: ${error.message}`);
    },
  });

  // Set default provider mutation
  const setDefaultMutation = useMutation({
    mutationFn: ragApi.setDefaultProvider,
    onSuccess: (_, provider) => {
      toast.success(`Set ${PROVIDER_INFO[provider]?.displayName || provider} as default provider`);
      refetchProviders();
      refetchSettings();
    },
    onError: (error: Error) => {
      toast.error(`Failed to set default: ${error.message}`);
    },
  });

  const handleSetDefaultProvider = (providerName: string) => {
    setDefaultMutation.mutate(providerName);
  };

  const handleRefreshProviders = async () => {
    await Promise.all([refetchProviders(), refetchHealth(), refetchSettings()]);
    toast.success('Provider status refreshed');
  };

  const handleConfigureProvider = (providerName: string) => {
    setSelectedProvider(providerName);
    setConfigDialogOpen(true);
  };

  const handleConfigSaved = () => {
    queryClient.invalidateQueries({ queryKey: ['rag-providers'] });
    queryClient.invalidateQueries({ queryKey: ['llm-settings'] });
    queryClient.invalidateQueries({ queryKey: ['rag-health'] });
  };

  // Helper to find settings for a provider
  const getProviderSettings = (providerName: string): LLMSettingsResponse | null => {
    return llmSettingsData?.settings.find((s) => s.provider === providerName) || null;
  };

  if (!user) {
    return (
      <Box>
        <Alert severity="error">You must be logged in to view settings.</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Settings
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
        Manage your account settings, preferences, and LLM configurations.
      </Typography>

      {/* Profile Section */}
      <ProfileSection
        user={user}
        onUpdate={(data) => updateUserMutation.mutate(data)}
        isUpdating={updateUserMutation.isPending}
      />

      {/* Password Section */}
      <PasswordSection
        onChangePassword={() => {
          // TODO: Implement password change API
          toast('Password change not implemented yet');
        }}
        isChanging={false}
      />

      {/* LLM Providers Section */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SmartToy color="primary" />
            <Typography variant="h6">LLM Providers</Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="outlined"
              startIcon={<Key />}
              onClick={() => setTestDialogOpen(true)}
            >
              Test API Key
            </Button>
            <Tooltip title="Refresh provider status">
              <IconButton onClick={handleRefreshProviders}>
                <Refresh />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        <Alert severity="info" sx={{ mb: 3 }} icon={<Info />}>
          <Typography variant="body2">
            <strong>Configure providers below</strong> by clicking "Set Up" or "Configure" on each provider card.
          </Typography>
          <Typography variant="body2" sx={{ mt: 1 }}>
            API keys are stored securely. Use the <strong>Test API Key</strong> button to verify keys before saving.
          </Typography>
        </Alert>

        {providersLoading || settingsLoading ? (
          <Grid container spacing={2}>
            {[1, 2, 3].map((i) => (
              <Grid item xs={12} md={6} lg={4} key={i}>
                <Skeleton variant="rectangular" height={200} />
              </Grid>
            ))}
          </Grid>
        ) : providersData ? (
          <Grid container spacing={2}>
            {providersData.providers.map((provider) => (
              <Grid item xs={12} md={6} lg={4} key={provider.name}>
                <ProviderCard
                  provider={provider}
                  settings={getProviderSettings(provider.name)}
                  isDefault={provider.name === providersData.default_provider}
                  onConfigure={() => handleConfigureProvider(provider.name)}
                  onSetDefault={() => handleSetDefaultProvider(provider.name)}
                />
              </Grid>
            ))}
          </Grid>
        ) : (
          <Alert severity="warning">Failed to load providers</Alert>
        )}
      </Paper>

      {/* System Health Section */}
      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
          <CheckCircle color="primary" />
          <Typography variant="h6">System Health</Typography>
        </Box>

        {healthData ? (
          <List>
            {Object.entries(healthData.components).map(([name, status]) => (
              <ListItem key={name}>
                <ListItemIcon>
                  {status.status === 'healthy' ? (
                    <CheckCircle color="success" />
                  ) : status.status === 'not_configured' ? (
                    <ErrorIcon color="warning" />
                  ) : (
                    <ErrorIcon color="error" />
                  )}
                </ListItemIcon>
                <ListItemText
                  primary={name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  secondary={status.error || (status.status === 'not_configured' ? 'Not configured' : 'Operating normally')}
                />
                <ListItemSecondaryAction>
                  <Chip
                    label={status.status}
                    size="small"
                    color={
                      status.status === 'healthy'
                        ? 'success'
                        : status.status === 'not_configured'
                        ? 'warning'
                        : 'error'
                    }
                    variant="outlined"
                  />
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        ) : (
          <Typography color="text.secondary">Loading system status...</Typography>
        )}
      </Paper>

      {/* Dialogs */}
      <ApiKeyTestDialog open={testDialogOpen} onClose={() => setTestDialogOpen(false)} />
      <ProviderConfigDialog
        open={configDialogOpen}
        onClose={() => {
          setConfigDialogOpen(false);
          setSelectedProvider(null);
        }}
        provider={selectedProvider}
        existingSettings={selectedProvider ? getProviderSettings(selectedProvider) : null}
        onSave={handleConfigSaved}
      />
    </Box>
  );
}
