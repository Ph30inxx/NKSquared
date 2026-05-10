import { NavLink } from "react-router-dom";
import DashboardIcon from "@mui/icons-material/Dashboard";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import BusinessCenterIcon from "@mui/icons-material/BusinessCenter";
import CurrencyExchangeIcon from "@mui/icons-material/CurrencyExchange";
import GridOnIcon from "@mui/icons-material/GridOn";
import HistoryIcon from "@mui/icons-material/History";
import InboxIcon from "@mui/icons-material/Inbox";
import ChatIcon from "@mui/icons-material/Chat";
import NotificationsActiveIcon from "@mui/icons-material/NotificationsActive";
import RuleIcon from "@mui/icons-material/Rule";
import Box from "@mui/material/Box";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Typography from "@mui/material/Typography";

import { useAuthStore } from "../../stores/auth";

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  end?: boolean;
  adminOnly?: boolean;
  section?: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: <DashboardIcon fontSize="small" />, end: true },
  { section: "Portfolio" },
  { to: "/portfolio", label: "Companies", icon: <BusinessCenterIcon fontSize="small" />, end: true },
  { to: "/grid", label: "Grid", icon: <GridOnIcon fontSize="small" />, end: true },
  { section: "MIS" },
  { to: "/mis", label: "Inbox", icon: <InboxIcon fontSize="small" />, end: true },
  { to: "/mis/templates", label: "Templates", icon: <RuleIcon fontSize="small" /> },
  { section: "Tools" },
  { to: "/ai-dashboard", label: "AI Dashboard", icon: <AutoAwesomeIcon fontSize="small" />, end: true },
  { to: "/chat", label: "Chat", icon: <ChatIcon fontSize="small" />, end: true },
  { section: "Admin" },
  { to: "/admin/reminders", label: "Reminders", icon: <NotificationsActiveIcon fontSize="small" />, end: true },
  { to: "/admin/audit-log", label: "Audit Log", icon: <HistoryIcon fontSize="small" />, end: true },
  {
    to: "/admin/forex-rates",
    label: "FX Rates",
    icon: <CurrencyExchangeIcon fontSize="small" />,
    end: true,
    adminOnly: true,
  },
] as NavItem[];

export default function SidebarNav() {
  const role = useAuthStore((s) => s.user?.role);

  return (
    <List disablePadding>
      {NAV_ITEMS.filter((item) => !("adminOnly" in item) || !item.adminOnly || role === "ADMIN").map(
        (item, idx) => {
          if ("section" in item && item.section) {
            return (
              <Box key={`section-${idx}`} sx={{ px: 2, pt: 2, pb: 0.5 }}>
                <Typography
                  variant="caption"
                  sx={{ fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "text.disabled" }}
                >
                  {item.section}
                </Typography>
              </Box>
            );
          }

          const navItem = item as NavItem & { to: string };
          return (
            <ListItemButton
              key={navItem.to}
              component={NavLink}
              to={navItem.to}
              end={navItem.end ?? false}
              sx={{
                borderRadius: 1.5,
                mx: 1,
                my: 0.25,
                px: 1.5,
                py: 0.875,
                gap: 1.25,
                "&.active": {
                  bgcolor: "primary.main",
                  "& .MuiListItemIcon-root": { color: "#fff" },
                  "& .MuiListItemText-primary": { color: "#fff", fontWeight: 700 },
                  "&:hover": { bgcolor: "primary.dark" },
                },
                "&:not(.active):hover": { bgcolor: "action.hover" },
              }}
            >
              <ListItemIcon sx={{ minWidth: 0, color: "text.secondary" }}>
                {navItem.icon}
              </ListItemIcon>
              <ListItemText
                primary={navItem.label}
                primaryTypographyProps={{ variant: "body2", fontWeight: 500 }}
              />
            </ListItemButton>
          );
        },
      )}
    </List>
  );
}
