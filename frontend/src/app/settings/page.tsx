"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import type { InviteUserResponse, Page, Role, UserOut } from "@/types/api";
import { UserPlus } from "lucide-react";

const ROLE_BADGE: Record<Role, "default" | "secondary" | "outline"> = {
  owner: "default",
  admin: "secondary",
  analyst: "outline",
  viewer: "outline",
};

function InviteMemberDialog() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [result, setResult] = useState<InviteUserResponse | null>(null);

  const invite = useMutation({
    mutationFn: () => api.post<InviteUserResponse>("/orgs/members", { email, full_name: fullName, role }),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["members"] });
    },
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setResult(null);
          setEmail("");
          setFullName("");
        }
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" className="gap-1.5">
          <UserPlus className="h-4 w-4" /> Invite member
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite a team member</DialogTitle>
        </DialogHeader>
        {result ? (
          <div className="space-y-3 text-sm">
            <p>{result.user.full_name} has been added. Share this temporary password with them:</p>
            <code className="block rounded-md bg-muted p-3 font-mono text-sm">{result.temporary_password}</code>
            <p className="text-xs text-muted-foreground">They should change it after first login.</p>
            <Button size="sm" onClick={() => setOpen(false)}>Done</Button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Full name</Label>
              <Input value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Email</Label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Role</Label>
              <Select value={role} onValueChange={(v) => setRole(v as Role)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="viewer">Viewer</SelectItem>
                  <SelectItem value="analyst">Analyst</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {invite.isError && (
              <p className="text-sm text-destructive">
                {invite.error instanceof ApiError ? invite.error.message : "Could not invite this member."}
              </p>
            )}
            <Button className="w-full" disabled={!email || !fullName || invite.isPending} onClick={() => invite.mutate()}>
              {invite.isPending ? "Inviting…" : "Send invite"}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function MembersList() {
  const { hasPermission } = useAuth();
  const { data, isLoading } = useQuery({
    queryKey: ["members"],
    queryFn: () => api.get<Page<UserOut>>("/orgs/members", { limit: 100 }),
  });

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;

  return (
    <div className="space-y-2">
      {data?.items.map((member) => (
        <div key={member.id} className="flex items-center justify-between rounded-md border p-3">
          <div>
            <p className="text-sm font-medium">{member.full_name}</p>
            <p className="text-xs text-muted-foreground">{member.email}</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={ROLE_BADGE[member.role]} className="capitalize">{member.role}</Badge>
            {!member.is_active && <Badge variant="secondary">Inactive</Badge>}
          </div>
        </div>
      ))}
      {hasPermission("member:invite") && (
        <p className="pt-2 text-xs text-muted-foreground">
          Members joined {data?.items[0] && formatDate(data.items[0].created_at)}
        </p>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const { user, organization, hasPermission } = useAuth();

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">Manage your workspace and team.</p>
      </div>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle className="text-base">Workspace</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex justify-between border-b pb-2">
            <span className="text-muted-foreground">Name</span>
            <span className="font-medium">{organization?.name}</span>
          </div>
          <div className="flex justify-between border-b pb-2">
            <span className="text-muted-foreground">Workspace URL</span>
            <span className="font-medium">{organization?.slug}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Your role</span>
            <span className="font-medium capitalize">{user?.role}</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="text-base">Team members</CardTitle>
            <CardDescription>Everyone with access to this workspace.</CardDescription>
          </div>
          {hasPermission("member:invite") && <InviteMemberDialog />}
        </CardHeader>
        <CardContent>
          <MembersList />
        </CardContent>
      </Card>
    </div>
  );
}
