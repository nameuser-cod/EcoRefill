import { useContext } from "react";
import { OwnerWorkspaceContext } from "./ownerWorkspaceContext";

export default function useOwnerMachine() {
  const workspace = useContext(OwnerWorkspaceContext);
  if (!workspace) throw new Error("Owner pages must be rendered inside OwnerWorkspace.");
  return workspace;
}
