/**
 * Auth Layout Component
 *
 * Layout wrapper for authentication pages (login, register).
 */

import { Box, Paper, Typography } from '@mui/material';
import { Email } from '@mui/icons-material';

interface AuthLayoutProps {
  children: React.ReactNode;
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
        p: 2,
      }}
    >
      <Paper
        elevation={0}
        sx={{
          p: 4,
          width: '100%',
          maxWidth: 440,
          borderRadius: 3,
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        {/* Logo */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 1.5,
            mb: 4,
          }}
        >
          <Box
            sx={{
              width: 48,
              height: 48,
              borderRadius: 2,
              bgcolor: 'primary.main',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Email sx={{ color: 'white', fontSize: 28 }} />
          </Box>
          <Box>
            <Typography variant="h5" fontWeight={700} lineHeight={1.2}>
              Email RAG
            </Typography>
            <Typography variant="caption" color="text.secondary">
              AI-Powered Email Analysis
            </Typography>
          </Box>
        </Box>

        {children}
      </Paper>
    </Box>
  );
}
