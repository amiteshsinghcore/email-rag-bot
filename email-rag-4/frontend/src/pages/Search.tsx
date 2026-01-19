/**
 * Search Page
 *
 * Email search interface with filters and results.
 */

import { useState, useCallback, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  TextField,
  InputAdornment,
  IconButton,
  Button,
  Chip,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  ListItemText,
  OutlinedInput,
  Collapse,
  Divider,
  List,
  ListItemButton,
  ListItemIcon,
  Skeleton,
  Alert,
  Pagination,
  Tooltip,
  Badge,
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList,
  Clear,
  Email as EmailIcon,
  AttachFile,
  Schedule,
  Person,
  ExpandMore,
  ExpandLess,
  History,
  PriorityHigh,
} from '@mui/icons-material';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { searchApi, uploadApi } from '@/services/api';
import { formatRelativeTime, truncate } from '@/utils';
import type { SearchQuery, SearchFilters, EmailSummary, PSTFile } from '@/types';

const IMPORTANCE_OPTIONS = [
  { value: 'low', label: 'Low', color: '#64748b' },
  { value: 'normal', label: 'Normal', color: '#6366f1' },
  { value: 'high', label: 'High', color: '#ef4444' },
];

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  onSearch: () => void;
  onClear: () => void;
  loading?: boolean;
}

function SearchBar({ value, onChange, onSearch, onClear, loading }: SearchBarProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      onSearch();
    }
  };

  return (
    <TextField
      fullWidth
      placeholder="Search emails by keyword, sender, subject..."
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={handleKeyDown}
      disabled={loading}
      InputProps={{
        startAdornment: (
          <InputAdornment position="start">
            <SearchIcon color="action" />
          </InputAdornment>
        ),
        endAdornment: value && (
          <InputAdornment position="end">
            <IconButton onClick={onClear} size="small">
              <Clear />
            </IconButton>
          </InputAdornment>
        ),
      }}
      sx={{
        '& .MuiOutlinedInput-root': {
          bgcolor: 'background.paper',
        },
      }}
    />
  );
}

interface FiltersProps {
  filters: SearchFilters;
  onFiltersChange: (filters: SearchFilters) => void;
  pstFiles: PSTFile[];
  expanded: boolean;
  onExpandChange: (expanded: boolean) => void;
}

function Filters({
  filters,
  onFiltersChange,
  pstFiles,
  expanded,
  onExpandChange,
}: FiltersProps) {
  const activeFiltersCount = Object.values(filters).filter(
    (v) => v !== undefined && (Array.isArray(v) ? v.length > 0 : true)
  ).length;

  const handlePstFilesChange = (value: string[]) => {
    onFiltersChange({ ...filters, pst_file_ids: value.length > 0 ? value : undefined });
  };

  const handleImportanceChange = (value: ('low' | 'normal' | 'high')[]) => {
    onFiltersChange({ ...filters, importance: value.length > 0 ? value : undefined });
  };

  const handleDateFromChange = (value: string) => {
    onFiltersChange({ ...filters, date_from: value || undefined });
  };

  const handleDateToChange = (value: string) => {
    onFiltersChange({ ...filters, date_to: value || undefined });
  };

  const handleSenderChange = (value: string) => {
    onFiltersChange({ ...filters, sender: value || undefined });
  };

  const handleHasAttachmentsChange = (value: boolean | undefined) => {
    onFiltersChange({ ...filters, has_attachments: value });
  };

  const clearFilters = () => {
    onFiltersChange({});
  };

  return (
    <Paper sx={{ p: 2, mb: 3 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
        }}
        onClick={() => onExpandChange(!expanded)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Badge badgeContent={activeFiltersCount} color="primary">
            <FilterList />
          </Badge>
          <Typography variant="subtitle1">Filters</Typography>
        </Box>
        <IconButton size="small">
          {expanded ? <ExpandLess /> : <ExpandMore />}
        </IconButton>
      </Box>

      <Collapse in={expanded}>
        <Divider sx={{ my: 2 }} />
        <Grid container spacing={2}>
          {/* PST Files */}
          <Grid item xs={12} md={6} lg={3}>
            <FormControl fullWidth size="small">
              <InputLabel>PST Files</InputLabel>
              <Select
                multiple
                value={filters.pst_file_ids || []}
                onChange={(e) => handlePstFilesChange(e.target.value as string[])}
                input={<OutlinedInput label="PST Files" />}
                renderValue={(selected) =>
                  selected.length === 0
                    ? 'All files'
                    : `${selected.length} selected`
                }
              >
                {pstFiles
                  .filter((f) => f.status === 'completed')
                  .map((file) => (
                    <MenuItem key={file.id} value={file.id}>
                      <Checkbox
                        checked={(filters.pst_file_ids || []).includes(file.id)}
                      />
                      <ListItemText
                        primary={file.original_filename}
                        secondary={`${file.email_count.toLocaleString()} emails`}
                      />
                    </MenuItem>
                  ))}
              </Select>
            </FormControl>
          </Grid>

          {/* Importance */}
          <Grid item xs={12} md={6} lg={3}>
            <FormControl fullWidth size="small">
              <InputLabel>Importance</InputLabel>
              <Select
                multiple
                value={filters.importance || []}
                onChange={(e) =>
                  handleImportanceChange(
                    e.target.value as ('low' | 'normal' | 'high')[]
                  )
                }
                input={<OutlinedInput label="Importance" />}
                renderValue={(selected) =>
                  selected.length === 0 ? 'Any' : selected.join(', ')
                }
              >
                {IMPORTANCE_OPTIONS.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    <Checkbox
                      checked={(filters.importance || []).includes(
                        option.value as 'low' | 'normal' | 'high'
                      )}
                    />
                    <ListItemText primary={option.label} />
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          {/* Date From */}
          <Grid item xs={12} md={6} lg={3}>
            <TextField
              fullWidth
              size="small"
              type="date"
              label="From Date"
              value={filters.date_from || ''}
              onChange={(e) => handleDateFromChange(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>

          {/* Date To */}
          <Grid item xs={12} md={6} lg={3}>
            <TextField
              fullWidth
              size="small"
              type="date"
              label="To Date"
              value={filters.date_to || ''}
              onChange={(e) => handleDateToChange(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>

          {/* Sender */}
          <Grid item xs={12} md={6} lg={3}>
            <TextField
              fullWidth
              size="small"
              label="Sender"
              placeholder="email@example.com"
              value={filters.sender || ''}
              onChange={(e) => handleSenderChange(e.target.value)}
            />
          </Grid>

          {/* Has Attachments */}
          <Grid item xs={12} md={6} lg={3}>
            <FormControl fullWidth size="small">
              <InputLabel>Attachments</InputLabel>
              <Select
                value={
                  filters.has_attachments === undefined
                    ? ''
                    : filters.has_attachments
                    ? 'yes'
                    : 'no'
                }
                onChange={(e) =>
                  handleHasAttachmentsChange(
                    e.target.value === ''
                      ? undefined
                      : e.target.value === 'yes'
                  )
                }
                label="Attachments"
              >
                <MenuItem value="">Any</MenuItem>
                <MenuItem value="yes">With attachments</MenuItem>
                <MenuItem value="no">Without attachments</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          {/* Clear Filters */}
          <Grid item xs={12} md={6} lg={6}>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', height: '100%' }}>
              <Button
                variant="outlined"
                onClick={clearFilters}
                disabled={activeFiltersCount === 0}
                startIcon={<Clear />}
              >
                Clear Filters
              </Button>
            </Box>
          </Grid>
        </Grid>
      </Collapse>
    </Paper>
  );
}

interface SearchResultItemProps {
  email: EmailSummary;
  onClick: () => void;
}

function SearchResultItem({ email, onClick }: SearchResultItemProps) {
  return (
    <ListItemButton
      onClick={onClick}
      sx={{
        borderRadius: 1,
        mb: 1,
        border: '1px solid',
        borderColor: 'divider',
        '&:hover': {
          bgcolor: 'action.hover',
        },
      }}
    >
      <ListItemIcon sx={{ minWidth: 40 }}>
        <EmailIcon color="action" />
      </ListItemIcon>
      <ListItemText
        primary={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body1" noWrap sx={{ flex: 1 }}>
              {email.subject || '(No Subject)'}
            </Typography>
            {email.importance === 'high' && (
              <Tooltip title="High importance">
                <PriorityHigh color="error" fontSize="small" />
              </Tooltip>
            )}
            {email.has_attachments && (
              <Tooltip title="Has attachments">
                <AttachFile fontSize="small" color="action" />
              </Tooltip>
            )}
          </Box>
        }
        secondary={
          <Box
            component="span"
            sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}
          >
            <Box
              component="span"
              sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
            >
              <Person fontSize="inherit" />
              <Typography variant="caption" component="span">
                {email.sender_name || email.sender}
              </Typography>
              <Schedule fontSize="inherit" sx={{ ml: 1 }} />
              <Typography variant="caption" component="span">
                {formatRelativeTime(email.date_sent)}
              </Typography>
            </Box>
            <Typography
              variant="body2"
              color="text.secondary"
              noWrap
              component="span"
            >
              {truncate(email.preview, 150)}
            </Typography>
          </Box>
        }
      />
    </ListItemButton>
  );
}

export function Search() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [query, setQuery] = useState(searchParams.get('q') || '');
  const [filters, setFilters] = useState<SearchFilters>({});
  const [filtersExpanded, setFiltersExpanded] = useState(false);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Load PST files for filter dropdown
  const { data: pstFiles = [] } = useQuery({
    queryKey: ['pst-files'],
    queryFn: uploadApi.getPSTFiles,
  });

  // Load search history (with error handling - not critical if it fails)
  const { data: searchHistory = [] } = useQuery({
    queryKey: ['search-history'],
    queryFn: searchApi.getSearchHistory,
    retry: false, // Don't retry on failure - not critical
    staleTime: 60000, // Cache for 1 minute
    refetchOnWindowFocus: false,
  });

  // Search mutation
  const searchMutation = useMutation({
    mutationFn: (searchQuery: SearchQuery) => searchApi.search(searchQuery),
  });

  const handleSearch = useCallback(() => {
    if (!query.trim()) return;

    setSearchParams({ q: query });
    setPage(1);
    searchMutation.mutate({
      query: query.trim(),
      filters,
      page: 1,
      page_size: pageSize,
    });
  }, [query, filters, searchMutation, setSearchParams]);

  const handleClear = useCallback(() => {
    setQuery('');
    setSearchParams({});
    searchMutation.reset();
  }, [setSearchParams, searchMutation]);

  const handlePageChange = useCallback(
    (_: React.ChangeEvent<unknown>, newPage: number) => {
      setPage(newPage);
      searchMutation.mutate({
        query: query.trim(),
        filters,
        page: newPage,
        page_size: pageSize,
      });
    },
    [query, filters, searchMutation]
  );

  const handleEmailClick = useCallback(
    (emailId: string) => {
      navigate(`/emails/${emailId}`);
    },
    [navigate]
  );

  const handleHistoryClick = useCallback(
    (historyQuery: string) => {
      setQuery(historyQuery);
      setSearchParams({ q: historyQuery });
      searchMutation.mutate({
        query: historyQuery,
        filters,
        page: 1,
        page_size: pageSize,
      });
    },
    [filters, searchMutation, setSearchParams]
  );

  // Trigger search when URL query changes
  useEffect(() => {
    const urlQuery = searchParams.get('q');
    if (urlQuery && urlQuery !== query) {
      setQuery(urlQuery);
      searchMutation.mutate({
        query: urlQuery,
        filters,
        page: 1,
        page_size: pageSize,
      });
    }
  }, [searchParams]);

  const results = searchMutation.data;
  const isLoading = searchMutation.isPending;
  const hasSearched = searchMutation.isSuccess || searchMutation.isError;

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Search Emails
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        Search through your indexed emails using natural language or keywords.
      </Typography>

      {/* Search Bar */}
      <Box sx={{ mb: 3 }}>
        <SearchBar
          value={query}
          onChange={setQuery}
          onSearch={handleSearch}
          onClear={handleClear}
          loading={isLoading}
        />
      </Box>

      {/* Filters */}
      <Filters
        filters={filters}
        onFiltersChange={setFilters}
        pstFiles={pstFiles}
        expanded={filtersExpanded}
        onExpandChange={setFiltersExpanded}
      />

      <Grid container spacing={3}>
        {/* Search Results */}
        <Grid item xs={12} lg={9}>
          {isLoading && (
            <Paper sx={{ p: 2 }}>
              {[...Array(5)].map((_, i) => (
                <Box key={i} sx={{ mb: 2 }}>
                  <Skeleton variant="rectangular" height={80} />
                </Box>
              ))}
            </Paper>
          )}

          {searchMutation.isError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              Failed to search. Please try again.
            </Alert>
          )}

          {!hasSearched && !isLoading && (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <SearchIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" gutterBottom>
                Start Searching
              </Typography>
              <Typography color="text.secondary">
                Enter a search term above to find emails
              </Typography>
            </Paper>
          )}

          {hasSearched && results && (
            <Paper sx={{ p: 2 }}>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  mb: 2,
                }}
              >
                <Typography variant="subtitle1">
                  {results.total.toLocaleString()} result
                  {results.total !== 1 ? 's' : ''} found
                  <Typography component="span" color="text.secondary" sx={{ ml: 1 }}>
                    ({results.query_time_ms}ms)
                  </Typography>
                </Typography>
              </Box>

              {results.emails.length === 0 ? (
                <Box sx={{ py: 4, textAlign: 'center' }}>
                  <Typography color="text.secondary">
                    No emails found matching your search criteria.
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Try adjusting your search terms or filters.
                  </Typography>
                </Box>
              ) : (
                <>
                  <List disablePadding>
                    {results.emails.map((email) => (
                      <SearchResultItem
                        key={email.id}
                        email={email}
                        onClick={() => handleEmailClick(email.id)}
                      />
                    ))}
                  </List>

                  {results.total_pages > 1 && (
                    <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
                      <Pagination
                        count={results.total_pages}
                        page={page}
                        onChange={handlePageChange}
                        color="primary"
                      />
                    </Box>
                  )}
                </>
              )}
            </Paper>
          )}
        </Grid>

        {/* Search History Sidebar */}
        <Grid item xs={12} lg={3}>
          <Paper sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <History fontSize="small" />
              <Typography variant="subtitle1">Recent Searches</Typography>
            </Box>
            <Divider sx={{ mb: 2 }} />

            {searchHistory.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                No recent searches
              </Typography>
            ) : (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {searchHistory.map((historyItem, index) => (
                  <Chip
                    key={index}
                    label={truncate(historyItem, 25)}
                    onClick={() => handleHistoryClick(historyItem)}
                    size="small"
                    variant="outlined"
                    sx={{ cursor: 'pointer' }}
                  />
                ))}
              </Box>
            )}
          </Paper>

          {/* Quick Tips */}
          <Paper sx={{ p: 2, mt: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              Search Tips
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <Typography variant="body2" color="text.secondary" paragraph>
              <strong>Natural language:</strong> "emails from John about the project"
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              <strong>Exact phrase:</strong> "quarterly report"
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              <strong>Sender:</strong> from:john@example.com
            </Typography>
            <Typography variant="body2" color="text.secondary">
              <strong>Date range:</strong> Use the filters above
            </Typography>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
