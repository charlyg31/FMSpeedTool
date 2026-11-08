// Yu-Gi-Oh! Forbidden Memories - image-analysis autosplitter (FM Speed Tool)
//
// This script does NOT read the game memory. It reads a small shared memory
// block ("FMSpeedTool_LiveSplit") written by FMSpeedTool.exe, which analyses
// the image of the ePSXe window and publishes there: start, splits, reset.
//
// Setup: LiveSplit > right click > Edit Layout... > (+) > Control >
// Scriptable Auto Splitter > Script Path: this file. FMSpeedTool.exe must be running.

state("FMSpeedTool") {}
state("python") {}

startup
{
    refreshRate = 60;

    settings.Add("split_win", true, "Split on win (campaign)");
    settings.Add("split_first_loss", true, "Split on first loss (Heishin 1)");
    settings.Add("split_farm", false, "Split at end of farm (back to menu)");
    settings.Add("split_other", true, "Split on a learned screen (\"Direct split\" action)");

    vars.view = null;
    vars.mmf = null;
    vars.startCount = 0;
    vars.splitCount = 0;
    vars.resetCount = 0;
    vars.oldStart = 0;
    vars.oldSplit = 0;
    vars.oldReset = 0;
    vars.kind = 0;
    vars.lastError = "";

    // Opens the shared block (fails while FMSpeedTool.exe is not running).
    vars.Open = (Func<bool>)(() =>
    {
        try
        {
            var mmf = System.IO.MemoryMappedFiles.MemoryMappedFile.OpenExisting("FMSpeedTool_LiveSplit");
            var view = mmf.CreateViewAccessor(0, 64, System.IO.MemoryMappedFiles.MemoryMappedFileAccess.Read);
            if (view.ReadInt32(0) != 0x54534D46) { view.Dispose(); mmf.Dispose(); return false; }
            vars.mmf = mmf;
            vars.view = view;
            // Start from the current counters: past events are not replayed.
            vars.startCount = vars.oldStart = view.ReadInt32(12);
            vars.splitCount = vars.oldSplit = view.ReadInt32(16);
            vars.resetCount = vars.oldReset = view.ReadInt32(20);
            print("[FMSpeedTool] connected to FMSpeedTool.exe");
            vars.lastError = "";
            return true;
        }
        catch (Exception e)
        {
            // Visible with DebugView; once per kind of error.
            if (vars.lastError != e.Message)
            {
                vars.lastError = e.Message;
                print("[FMSpeedTool] waiting for FMSpeedTool.exe: " + e.Message);
            }
            return false;
        }
    });

    vars.Close = (Action)(() =>
    {
        if (vars.view != null) { vars.view.Dispose(); vars.view = null; }
        if (vars.mmf != null) { vars.mmf.Dispose(); vars.mmf = null; }
    });
}

init
{
    vars.Close();
}

update
{
    if (vars.view == null && !vars.Open())
        return false;

    vars.oldStart = vars.startCount;
    vars.oldSplit = vars.splitCount;
    vars.oldReset = vars.resetCount;
    try
    {
        vars.startCount = vars.view.ReadInt32(12);
        vars.splitCount = vars.view.ReadInt32(16);
        vars.resetCount = vars.view.ReadInt32(20);
        vars.kind = vars.view.ReadInt32(24);
    }
    catch
    {
        vars.Close();          // FMSpeedTool.exe closed: reconnect later
        return false;
    }
    return true;
}

start
{
    return vars.startCount != vars.oldStart;
}

reset
{
    return vars.resetCount != vars.oldReset;
}

split
{
    if (vars.splitCount == vars.oldSplit)
        return false;
    int kind = vars.kind;
    if (kind == 1) return settings["split_win"];
    if (kind == 2) return settings["split_first_loss"];
    if (kind == 3) return settings["split_farm"];
    return settings["split_other"];
}

exit
{
    vars.Close();
}

shutdown
{
    vars.Close();
}
