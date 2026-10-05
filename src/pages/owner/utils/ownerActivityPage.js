export const OWNER_ACTIVITY_PAGE_SIZE = 30;

export function paginateOwnerActivity(records, requestedPage, pageSize = OWNER_ACTIVITY_PAGE_SIZE) {
  const totalPages = Math.max(1, Math.ceil(records.length / pageSize));
  const page = Math.min(totalPages, Math.max(1, Math.trunc(requestedPage) || 1));
  const offset = (page - 1) * pageSize;
  return { page, totalPages, offset, items: records.slice(offset, offset + pageSize) };
}
