import { IconEdit } from "@tabler/icons-react";
import { useEffect, useState } from "react";

export const descriptionMaxLength = 280;

export default function DescriptionEditor({
  description,
  editable,
  emptyText,
  onSave,
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(description ?? "");
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isEditing) {
      setDraft(description ?? "");
    }
  }, [description, isEditing]);

  const remaining = descriptionMaxLength - draft.length;

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setSaving(true);

    try {
      await onSave(draft);
      setIsEditing(false);
    } catch (saveError) {
      setError(saveError.message || "Description could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  if (isEditing) {
    return (
      <form className="description-editor" onSubmit={handleSubmit}>
        <textarea
          aria-label="Description"
          className="description-editor-input"
          maxLength={descriptionMaxLength}
          onChange={(event) => setDraft(event.target.value)}
          rows={3}
          value={draft}
        />
        <div className="description-editor-footer">
          <span className={remaining < 0 ? "error" : undefined}>
            {remaining} characters left
          </span>
          <span className="description-editor-actions">
            <button
              type="button"
              className="description-cancel-button"
              onClick={() => {
                setDraft(description ?? "");
                setError(null);
                setIsEditing(false);
              }}
              disabled={saving}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="description-save-button"
              disabled={saving || draft.length > descriptionMaxLength}
            >
              Save
            </button>
          </span>
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </form>
    );
  }

  function startEditing() {
    setError(null);
    setIsEditing(true);
  }

  if (!description && editable) {
    return (
      <button
        type="button"
        className="add-description-button"
        onClick={startEditing}
      >
        <IconEdit size={14} stroke={1.75} aria-hidden="true" />
        <span>{emptyText}</span>
      </button>
    );
  }

  return (
    <div className="profile-description-row">
      <p
        className={
          description
            ? "profile-description"
            : `profile-description ${editable ? "empty" : "muted"}`
        }
      >
        {description || emptyText}
      </p>
      {editable && (
        <button
          type="button"
          className="icon-button secondary"
          onClick={startEditing}
          aria-label="Edit description"
          title="Edit description"
        >
          <IconEdit size={17} stroke={1.75} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
