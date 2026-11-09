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

    vars.view = null;
    vars.mmf = null;
    vars.startCount = 0;
    vars.splitCount = 0;
    vars.resetCount = 0;
    vars.oldStart = 0;
    vars.oldSplit = 0;
    vars.oldReset = 0;
    vars.kind = 0;
    vars.saveCount = 0;
    vars.loadCount = 0;
    vars.savedIndex = -1;      // split index at the last in-game save (SAVE COMPLETE!)
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
            bool v2 = view.ReadInt32(4) >= 2;
            vars.saveCount = v2 ? view.ReadInt32(56) : 0;
            vars.loadCount = v2 ? view.ReadInt32(60) : 0;
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
        // Save/load counters exist from version 2 (before, bytes 56-63 held the opponent name).
        bool v2 = vars.view.ReadInt32(4) >= 2;
        int saves = v2 ? vars.view.ReadInt32(56) : 0;
        int loads = v2 ? vars.view.ReadInt32(60) : 0;
        if (timer.CurrentPhase == TimerPhase.NotRunning)
            vars.savedIndex = -1;
        // In-game save: remember where the run is.
        if (saves != vars.saveCount && timer.CurrentPhase != TimerPhase.NotRunning)
            vars.savedIndex = timer.CurrentSplitIndex;
        // Save loaded (FM Speed Tool set to "undo"): undo the splits made since that save.
        if (loads != vars.loadCount && vars.savedIndex >= 0)
        {
            var model = new TimerModel { CurrentState = timer };
            int target = vars.savedIndex;
            int guard = 100;
            while (timer.CurrentPhase != TimerPhase.NotRunning && timer.CurrentSplitIndex > target && guard-- > 0)
                model.UndoSplit();
            print("[FMSpeedTool] save loaded: back to split " + target);
        }
        vars.saveCount = saves;
        vars.loadCount = loads;
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
    return false;
}

exit
{
    vars.Close();
}

shutdown
{
    vars.Close();
}
