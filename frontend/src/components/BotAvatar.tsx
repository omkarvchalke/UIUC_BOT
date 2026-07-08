export default function BotAvatar() {
  return (
    <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-brand-600 text-white">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="h-4.5 w-4.5"
      >
        <rect x="3" y="8" width="18" height="12" rx="2" />
        <circle cx="8.5" cy="14" r="1.2" fill="currentColor" stroke="none" />
        <circle cx="15.5" cy="14" r="1.2" fill="currentColor" stroke="none" />
        <path d="M12 8V4" />
        <circle cx="12" cy="3" r="1" fill="currentColor" stroke="none" />
      </svg>
    </div>
  );
}
