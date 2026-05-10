import { createTheme, alpha } from "@mui/material/styles";

const PRIMARY = "#1B4FD8"; // rich indigo-blue
const PRIMARY_DARK = "#1340B0";
const PRIMARY_LIGHT = "#4F75E8";

const theme = createTheme({
  palette: {
    primary: {
      main: PRIMARY,
      dark: PRIMARY_DARK,
      light: PRIMARY_LIGHT,
      contrastText: "#ffffff",
    },
    background: {
      default: "#F4F6FA",
      paper: "#FFFFFF",
    },
    text: {
      primary: "#111827",
      secondary: "#6B7280",
      disabled: "#9CA3AF",
    },
    divider: "#E5E7EB",
    success: { main: "#059669", contrastText: "#fff" },
    error:   { main: "#DC2626", contrastText: "#fff" },
    warning: { main: "#D97706", contrastText: "#fff" },
    info:    { main: "#0284C7", contrastText: "#fff" },
  },

  typography: {
    fontFamily: [
      "Inter",
      "-apple-system",
      "BlinkMacSystemFont",
      "Segoe UI",
      "Roboto",
      "sans-serif",
    ].join(","),
    h4: { fontWeight: 700, fontSize: "1.5rem", letterSpacing: "-0.02em" },
    h5: { fontWeight: 700, fontSize: "1.25rem", letterSpacing: "-0.01em" },
    h6: { fontWeight: 600, fontSize: "1rem", letterSpacing: "-0.01em" },
    subtitle1: { fontWeight: 500, fontSize: "0.9375rem" },
    subtitle2: { fontWeight: 600, fontSize: "0.8125rem" },
    body1: { fontSize: "0.9375rem", lineHeight: 1.6 },
    body2: { fontSize: "0.875rem", lineHeight: 1.5 },
    caption: { fontSize: "0.75rem", letterSpacing: "0.01em" },
    button: { textTransform: "none", fontWeight: 600, letterSpacing: "0.01em" },
  },

  shape: { borderRadius: 8 },

  shadows: [
    "none",
    "0 1px 2px 0 rgba(0,0,0,0.05)",
    "0 1px 3px 0 rgba(0,0,0,0.08), 0 1px 2px -1px rgba(0,0,0,0.06)",
    "0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05)",
    "0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.05)",
    "0 20px 25px -5px rgba(0,0,0,0.08), 0 8px 10px -6px rgba(0,0,0,0.04)",
    "0 25px 50px -12px rgba(0,0,0,0.18)",
    "0 25px 50px -12px rgba(0,0,0,0.20)",
    "0 25px 50px -12px rgba(0,0,0,0.22)",
    "0 25px 50px -12px rgba(0,0,0,0.24)",
    "0 25px 50px -12px rgba(0,0,0,0.26)",
    "0 25px 50px -12px rgba(0,0,0,0.28)",
    "0 25px 50px -12px rgba(0,0,0,0.30)",
    "0 25px 50px -12px rgba(0,0,0,0.32)",
    "0 25px 50px -12px rgba(0,0,0,0.34)",
    "0 25px 50px -12px rgba(0,0,0,0.36)",
    "0 25px 50px -12px rgba(0,0,0,0.38)",
    "0 25px 50px -12px rgba(0,0,0,0.40)",
    "0 25px 50px -12px rgba(0,0,0,0.42)",
    "0 25px 50px -12px rgba(0,0,0,0.44)",
    "0 25px 50px -12px rgba(0,0,0,0.46)",
    "0 25px 50px -12px rgba(0,0,0,0.48)",
    "0 25px 50px -12px rgba(0,0,0,0.50)",
    "0 25px 50px -12px rgba(0,0,0,0.52)",
    "0 25px 50px -12px rgba(0,0,0,0.54)",
  ],

  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          scrollbarWidth: "thin",
          scrollbarColor: "#D1D5DB transparent",
          "&::-webkit-scrollbar": { width: 6, height: 6 },
          "&::-webkit-scrollbar-track": { background: "transparent" },
          "&::-webkit-scrollbar-thumb": { background: "#D1D5DB", borderRadius: 3 },
        },
      },
    },

    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 6, paddingTop: 7, paddingBottom: 7 },
        sizeSmall: { paddingTop: 4, paddingBottom: 4, fontSize: "0.8125rem" },
        sizeLarge: { paddingTop: 11, paddingBottom: 11, fontSize: "1rem" },
        containedPrimary: {
          background: `linear-gradient(135deg, ${PRIMARY_LIGHT} 0%, ${PRIMARY} 60%, ${PRIMARY_DARK} 100%)`,
          "&:hover": {
            background: `linear-gradient(135deg, ${PRIMARY} 0%, ${PRIMARY_DARK} 100%)`,
          },
        },
      },
    },

    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          border: "1px solid #E5E7EB",
          backgroundImage: "none",
        },
        elevation1: {
          boxShadow: "0 1px 3px 0 rgba(0,0,0,0.08), 0 1px 2px -1px rgba(0,0,0,0.06)",
          border: "none",
        },
        elevation2: {
          boxShadow: "0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05)",
          border: "none",
        },
      },
    },

    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: { border: "1px solid #E5E7EB" },
      },
    },

    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 500, fontSize: "0.75rem" },
        sizeSmall: { height: 22 },
      },
    },

    MuiTextField: {
      defaultProps: { size: "small" },
    },

    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          "&:hover .MuiOutlinedInput-notchedOutline": {
            borderColor: PRIMARY_LIGHT,
          },
        },
        notchedOutline: { borderColor: "#D1D5DB" },
      },
    },

    MuiTableHead: {
      styleOverrides: {
        root: {
          "& .MuiTableCell-head": {
            fontWeight: 600,
            fontSize: "0.75rem",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            color: "#6B7280",
            backgroundColor: "#F9FAFB",
            borderBottom: "1px solid #E5E7EB",
          },
        },
      },
    },

    MuiTableCell: {
      styleOverrides: {
        root: { borderColor: "#F3F4F6", padding: "10px 16px" },
        sizeSmall: { padding: "8px 12px" },
      },
    },

    MuiTableRow: {
      styleOverrides: {
        root: {
          "&:last-child td": { borderBottom: 0 },
          "&.MuiTableRow-hover:hover": { backgroundColor: "#F9FAFB" },
        },
      },
    },

    MuiAppBar: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        colorDefault: {
          backgroundColor: "#FFFFFF",
          borderBottom: "1px solid #E5E7EB",
        },
      },
    },

    MuiDrawer: {
      styleOverrides: {
        paper: { borderRight: "1px solid #E5E7EB", backgroundColor: "#FFFFFF" },
      },
    },

    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          margin: "1px 8px",
          padding: "7px 10px",
          "&.Mui-selected": {
            backgroundColor: alpha(PRIMARY, 0.08),
            "&:hover": { backgroundColor: alpha(PRIMARY, 0.12) },
          },
          "&:hover": { backgroundColor: "#F3F4F6" },
        },
      },
    },

    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: 8, fontSize: "0.875rem" },
      },
    },

    MuiDialog: {
      styleOverrides: {
        paper: { borderRadius: 12, border: "none" },
      },
    },

    MuiDialogTitle: {
      styleOverrides: {
        root: { fontWeight: 700, fontSize: "1.0625rem" },
      },
    },

    MuiToggleButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          fontWeight: 500,
          fontSize: "0.8125rem",
          borderRadius: "6px !important",
        },
      },
    },

    MuiToggleButtonGroup: {
      styleOverrides: {
        root: { gap: 2 },
        grouped: { border: "1px solid #D1D5DB !important", margin: "0 !important" },
      },
    },

    MuiTooltip: {
      defaultProps: { arrow: true },
      styleOverrides: {
        tooltip: { fontSize: "0.75rem", fontWeight: 500 },
      },
    },

    MuiDivider: {
      styleOverrides: { root: { borderColor: "#E5E7EB" } },
    },

    MuiSkeleton: {
      defaultProps: { animation: "wave" },
    },

    MuiCircularProgress: {
      defaultProps: { size: 32 },
    },

    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: "none",
          fontWeight: 600,
          fontSize: "0.875rem",
          minHeight: 44,
        },
      },
    },

    MuiTabs: {
      styleOverrides: {
        indicator: { height: 3, borderRadius: 2 },
      },
    },

    MuiSelect: {
      defaultProps: { size: "small" },
    },

    MuiFormControl: {
      defaultProps: { size: "small" },
    },

    MuiInputLabel: {
      defaultProps: { size: "small" },
    },
  },
});

export default theme;
