import { ProtectedShell } from "@/components/dashboard/protected-shell";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return <ProtectedShell>{children}</ProtectedShell>;
}
