import { NavLink } from "react-router-dom";
import DashboardIcon from "@mui/icons-material/Dashboard";
import BusinessCenterIcon from "@mui/icons-material/BusinessCenter";
import CurrencyExchangeIcon from "@mui/icons-material/CurrencyExchange";
import GridOnIcon from "@mui/icons-material/GridOn";
import InboxIcon from "@mui/icons-material/Inbox";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";

import { useAuthStore } from "../../stores/auth";

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: <DashboardIcon /> },
  { to: "/portfolio", label: "Portfolio", icon: <BusinessCenterIcon /> },
  { to: "/grid", label: "Grid", icon: <GridOnIcon /> },
  { to: "/mis", label: "MIS", icon: <InboxIcon /> },
  {
    to: "/admin/forex-rates",
    label: "FX rates",
    icon: <CurrencyExchangeIcon />,
    adminOnly: true,
  },
];

export default function SidebarNav() {
  const role = useAuthStore((s) => s.user?.role);

  return (
    <List>
      {NAV_ITEMS.filter((item) => !item.adminOnly || role === "ADMIN").map((item) => (
        <ListItemButton
          key={item.to}
          component={NavLink}
          to={item.to}
          end={item.to === "/"}
          sx={{
            "&.active": {
              bgcolor: "action.selected",
              "& .MuiListItemIcon-root, & .MuiListItemText-primary": {
                color: "primary.main",
                fontWeight: 600,
              },
            },
          }}
        >
          <ListItemIcon>{item.icon}</ListItemIcon>
          <ListItemText primary={item.label} />
        </ListItemButton>
      ))}
    </List>
  );
}
