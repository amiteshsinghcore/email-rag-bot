/**
 * Not Found Page
 *
 * 404 error page.
 */

import { Box, Typography, Button } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { Home, ArrowBack } from '@mui/icons-material';

export function NotFound() {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        textAlign: 'center',
        p: 3,
      }}
    >
      <Typography
        variant="h1"
        sx={{
          fontSize: '8rem',
          fontWeight: 700,
          color: 'primary.main',
          mb: 2,
        }}
      >
        404
      </Typography>
      <Typography variant="h4" gutterBottom>
        Page Not Found
      </Typography>
      <Typography
        variant="body1"
        color="text.secondary"
        sx={{ mb: 4, maxWidth: 400 }}
      >
        The page you're looking for doesn't exist or has been moved.
      </Typography>
      <Box sx={{ display: 'flex', gap: 2 }}>
        <Button
          variant="outlined"
          startIcon={<ArrowBack />}
          onClick={() => window.history.back()}
        >
          Go Back
        </Button>
        <Button
          component={RouterLink}
          to="/dashboard"
          variant="contained"
          startIcon={<Home />}
        >
          Go to Dashboard
        </Button>
      </Box>
    </Box>
  );
}
