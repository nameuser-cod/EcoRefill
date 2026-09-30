function PhotoActivityRow({ className, onOpen, children }) {
  return (
    <div
      className={`${className}${onOpen ? " view-photos-button" : ""}`}
      role={onOpen ? "button" : undefined}
      tabIndex={onOpen ? 0 : undefined}
      aria-haspopup={onOpen ? "dialog" : undefined}
      onClick={onOpen}
      onKeyDown={onOpen ? (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      } : undefined}
    >
      {children}
    </div>
  );
}

export default PhotoActivityRow;
