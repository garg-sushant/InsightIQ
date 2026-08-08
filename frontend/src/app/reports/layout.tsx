import { ProtectedShell } from "@/components/dashboard/protected-shell";

export default function ReportsLayout({ children }: { children: React.ReactNode }) {
  return <ProtectedShell>{children}</ProtectedShell>;
}
