import { ProtectedShell } from "@/components/dashboard/protected-shell";

export default function DatasetsLayout({ children }: { children: React.ReactNode }) {
  return <ProtectedShell>{children}</ProtectedShell>;
}
