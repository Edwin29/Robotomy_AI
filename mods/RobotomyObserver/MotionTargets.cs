using System.Collections.Generic;
using UnityEngine;

// Shipped display-component adapters, not model enumeration. CreatureLayer creates
// both ordinary and Ordeal/Event bodies as CreatureUnit; ChildCreatureUnit inherits it.
// The per-capture index also serves occlusion ownership, avoiding repeated scene scans
// and parent walks for each candidate surface patch. Never cache across game frames.
public sealed class MotionTargets
{
    readonly Dictionary<Transform,MonoBehaviour> owners = new Dictionary<Transform,MonoBehaviour>();
    public readonly Dictionary<Transform,Spine.Unity.SkeletonRenderer> Skeletons =
        new Dictionary<Transform,Spine.Unity.SkeletonRenderer>();
    public int UnsupportedRenderers;

    static bool Supported(MonoBehaviour value) {
        return value is WorkerUnit || value is CreatureUnit || value is ProjectileUnit ||
            value is SlimeGirlProjectile || value is SlimeGirlWeaponProjectile ||
            value is MagicalGirlWeaponProjectile || value is GeburahProjectile ||
            value is BinahBoss.BinahProjectile;
    }
    MonoBehaviour Owner(Transform node) {
        if(node==null) return null;
        MonoBehaviour result;
        if(owners.TryGetValue(node,out result)) return result;
        foreach(var component in node.GetComponents<MonoBehaviour>())
            if(Supported(component)) { result=component; owners[node]=result; return result; }
        result=Owner(node.parent); owners[node]=result; return result;
    }
    public UnityEngine.Object Owner(Renderer renderer) { return renderer==null?null:Owner(renderer.transform); }

    static Transform DisplayRoot(MonoBehaviour owner) {
        var worker=owner as WorkerUnit;
        if(worker!=null) return worker.spineRenderer==null?null:worker.spineRenderer.transform;
        var creature=owner as CreatureUnit;
        if(creature!=null) return creature.animTarget==null?null:creature.animTarget.transform;
        var projectile=owner as ProjectileUnit;
        if(projectile!=null) return projectile.animTarget==null?null:projectile.animTarget.transform;
        var slime=owner as SlimeGirlProjectile;
        if(slime!=null) return slime._effect;
        var slimeWeapon=owner as SlimeGirlWeaponProjectile;
        if(slimeWeapon!=null) return slimeWeapon._effect;
        var magic=owner as MagicalGirlWeaponProjectile;
        if(magic!=null) return magic._effect;
        var geburah=owner as GeburahProjectile;
        if(geburah!=null) return geburah.animator==null?null:geburah.animator.transform;
        var binah=owner as BinahBoss.BinahProjectile;
        if(binah!=null) return binah.animator==null?null:binah.animator.transform;
        return null;
    }
    public MotionTargets(Renderer[] renderers) {
        foreach(var renderer in renderers) {
            if(renderer==null) continue;
            MonoBehaviour owner=Owner(renderer.transform);
            if(owner==null) continue;
            Transform root=DisplayRoot(owner);
            // Never infer a body from unrelated health bars, selection markers or
            // arbitrary descendants of a unit. Only its explicit visual branch.
            if(root==null || !renderer.transform.IsChildOf(root)) continue;
            var skeleton=renderer.GetComponentInParent<Spine.Unity.SkeletonRenderer>();
            if(skeleton==null || !skeleton.transform.IsChildOf(root)) { UnsupportedRenderers++; continue; }
            // A projectile can move a display child while its controller is stationary.
            // Track the display transform itself, not the controller/model position.
            // Separate Spine display branches are independently visible objects.
            Skeletons[skeleton.transform]=skeleton;
        }
    }
}
